#!/usr/bin/env bash
# Bootstrap all per-framework virtual environments (and, optionally, native
# builds) needed to run benchmark_all.py on a fresh machine.
#
# The frameworks under benchmark do NOT share one venv: they require
# different Python versions and mutually incompatible package versions
# (e.g. brand-tutorial pins numpy==1.18/torch==1.12 on Python 3.8, while
# dareplane/falcon/zeromq/bifrost use numpy==2.x/torch==2.x on Python 3.12).
# So this script creates one venv per framework, matching what
# benchmark_all.py already expects (venv name + subfolder).
#
# Usage:
#   ./bootstrap.sh [--force] [--with-builds] [--with-system-deps] [--only NAME]
#
#   --force              Recreate venvs that already exist.
#   --with-builds        Also run each framework's native build step
#                         (make/cmake). Off by default.
#   --with-system-deps   Also install apt packages / setcap needed by the
#                         native builds (falcon, zeromq). Runs sudo. Off by
#                         default; without it the script just tells you what
#                         to install.
#   --only NAME          Only bootstrap one framework (e.g. --only falcon).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY312="python3.12"
PY38="python3.8"

FORCE=0
WITH_BUILDS=0
WITH_SYSTEM_DEPS=0
ONLY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) FORCE=1; shift ;;
        --with-builds) WITH_BUILDS=1; shift ;;
        --with-system-deps) WITH_SYSTEM_DEPS=1; shift ;;
        --only) ONLY="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | sed 's/^#//'; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

log() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33m!! %s\033[0m\n' "$1" >&2; }

should_run() {
    [[ -z "$ONLY" || "$ONLY" == "$1" ]]
}

require_python() {
    local py="$1"
    if ! command -v "$py" >/dev/null 2>&1; then
        warn "$py not found on PATH — install it before bootstrapping this framework."
        return 1
    fi
}

create_venv() {
    local name="$1" dir="$2" venv_name="$3" py="$4" pre_install_hook="${5:-}"
    should_run "$name" || return 0
    require_python "$py" || return 0

    log "$name: venv ($venv_name, $py)"
    local venv_path="$ROOT/$dir/$venv_name"

    if [[ -x "$venv_path/bin/pip" && "$FORCE" -eq 0 ]]; then
        echo "  already exists, skipping (use --force to recreate)"
    else
        rm -rf "$venv_path"
        "$py" -m venv "$venv_path"
        "$venv_path/bin/pip" install --upgrade pip --quiet
    fi

    if [[ -n "$pre_install_hook" ]]; then
        "$pre_install_hook" "$venv_path"
    fi

    local req="$ROOT/$dir/requirements.txt"
    if [[ -f "$req" ]]; then
        "$venv_path/bin/pip" install -r "$req"
    else
        echo "  no requirements.txt in $dir, skipping pip install"
    fi
}

# bifrost's Python package can't be pip-installed on its own: its setup.py
# reads bifrost/version/__init__.py, which only exists after `./configure &&
# make` has run against a checked-out copy of the source — pip's own
# git+https editable install clones fresh and immediately tries to build,
# with no hook to run configure/make first. So we clone+build it ourselves
# into bifrost/vendor/bifrost-src (gitignored, not committed — same pinned
# commit bifrost/requirements.txt's local -e path points at) before bifrost's
# requirements.txt install runs. No CUDA toolchain is required for this
# benchmark — the vendored source is configured with --disable-cuda.
BIFROST_COMMIT="58df784dc467a2f538035c8d8412d60ce18e8b0a"
BIFROST_URL="https://github.com/lbeland/bifrost.git"

prepare_bifrost_vendor() {
    local venv_path="$1"
    local src_dir="$ROOT/bifrost/vendor/bifrost-src"
    local version_file="$src_dir/python/bifrost/version/__init__.py"

    if [[ -f "$version_file" ]]; then
        echo "  bifrost vendor already built, skipping (delete $version_file to force a rebuild)"
        return 0
    fi

    if [[ ! -d "$src_dir" ]]; then
        echo "  cloning bifrost@${BIFROST_COMMIT:0:12} into $src_dir..."
        mkdir -p "$(dirname "$src_dir")"
        git clone --quiet "$BIFROST_URL" "$src_dir"
        git -C "$src_dir" checkout --quiet "$BIFROST_COMMIT"
        rm -rf "$src_dir/.git"
    fi

    echo "  building bifrost (CPU-only, --disable-cuda) to generate Python bindings..."
    "$venv_path/bin/pip" install --quiet ctypesgen==1.0.2 setuptools
    (
        cd "$src_dir"
        ./configure --disable-cuda --with-python="$venv_path/bin/python3"
        make -j"$(nproc)"
    )
}

# ---- system packages (only with --with-system-deps) -----------------------

system_deps() {
    should_run "system-deps" || return 0
    [[ "$WITH_SYSTEM_DEPS" -eq 1 ]] || {
        warn "Skipping system packages. zeromq_diy/falcon need: libzmq3-dev, gcc-14, g++-14."
        warn "licorice needs: libevent-dev, libmsgpack-dev."
        warn "Re-run with --with-system-deps to install them via apt (requires sudo)."
        return 0
    }
    log "system packages (apt)"
    sudo apt-get update
    sudo apt-get install -y libzmq3-dev gcc-14 g++-14 libevent-dev libmsgpack-dev
}

# ---- native builds (only with --with-builds) -------------------------------

build_zeromq_diy() {
    should_run "zeromq_diy" || return 0
    [[ "$WITH_BUILDS" -eq 1 ]] || return 0
    log "zeromq_diy: make"
    make -j"$(nproc)" -C "$ROOT/zeromq_diy"
}

build_dareplane() {
    should_run "dareplane" || return 0
    [[ "$WITH_BUILDS" -eq 1 ]] || return 0
    log "dareplane: make (recursive, builds c-producer/c-consumer)"
    make -j"$(nproc)" -C "$ROOT/dareplane"
}

build_brand_tutorial() {
    should_run "brand-tutorial" || return 0
    [[ "$WITH_BUILDS" -eq 1 ]] || return 0
    log "brand-tutorial: make (builds redis-server/redis-cli, hiredis, and the benchmark nodes)"

    # The vendored jemalloc source under brand/lib/redis/deps/jemalloc is
    # missing bin/{jemalloc-config,jemalloc.sh,jeprof}.in (incomplete
    # vendoring upstream), so its own ./configure fails with "cannot find
    # input file: bin/jemalloc-config.in", which then cascades into every
    # redis src/*.c file failing with "jemalloc/jemalloc.h: No such file or
    # directory". These are untracked local files, so they don't survive a
    # `git submodule update`/re-clone of brand/lib/redis — recreate them
    # from upstream jemalloc (a public repo) if missing.
    local jemalloc_dir="$ROOT/brand-tutorial/brand/lib/redis/deps/jemalloc"
    if [[ -d "$jemalloc_dir" && ! -f "$jemalloc_dir/bin/jemalloc-config.in" ]]; then
        echo "  fetching missing jemalloc bin/ templates from upstream..."
        local tmp_jemalloc
        tmp_jemalloc="$(mktemp -d)"
        git clone --quiet --depth 1 https://github.com/jemalloc/jemalloc.git "$tmp_jemalloc"
        mkdir -p "$jemalloc_dir/bin"
        cp "$tmp_jemalloc/bin/jemalloc-config.in" "$tmp_jemalloc/bin/jemalloc.sh.in" "$tmp_jemalloc/bin/jeprof.in" "$jemalloc_dir/bin/"
        rm -rf "$tmp_jemalloc"
    fi
    # jemalloc's own ./configure is generated by autoconf from configure.ac
    # and is (correctly) gitignored/untracked, so it's also missing after a
    # fresh checkout — deps/Makefile's "-(cd ../deps && make ...)" call
    # silently fails without it (its exit code is ignored), which is what
    # cascades into the confusing "jemalloc/jemalloc.h: No such file" error
    # in redis's own src/ compilation.
    if [[ -d "$jemalloc_dir" && ! -f "$jemalloc_dir/configure" ]]; then
        echo "  running autoconf for jemalloc..."
        ( cd "$jemalloc_dir" && autoconf )
    fi
    # redis/src/Makefile is supposed to build these deps itself via a
    # "-(cd ../deps && make ...)" line in its persist-settings target, but
    # that line's exit code is deliberately ignored, so a failure there
    # (e.g. jemalloc/jemalloc.h missing) silently falls through straight
    # into compiling src/*.c against headers that were never built. Build
    # them explicitly ourselves first so that step is a no-op either way.
    if [[ ! -f "$jemalloc_dir/lib/libjemalloc.a" ]]; then
        echo "  building redis deps (hiredis, linenoise, lua, hdr_histogram, jemalloc)..."
        make -C "$ROOT/brand-tutorial/brand/lib/redis/deps" hiredis linenoise lua hdr_histogram jemalloc
    fi

    # Not run with -j: redis's own Makefile doesn't correctly order its
    # deps (jemalloc etc.) before compiling src/, so parallel jobs race
    # and redis src files can start before jemalloc's headers exist.
    # PATH needs the rt venv's bin/ so the benchmark nodes' Makefiles can
    # find `cython` (used to compile the python producer/consumer nodes
    # into embedded C binaries).
    PATH="$ROOT/brand-tutorial/rt/bin:$PATH" make -C "$ROOT/brand-tutorial/brand"
}

build_falcon() {
    should_run "falcon-core-develop" || return 0
    [[ "$WITH_BUILDS" -eq 1 ]] || return 0
    log "falcon-core-develop: cmake + make"
    local build_dir="$ROOT/falcon-core-develop/build"
    local venv_cmake="$ROOT/falcon-core-develop/venv/bin/cmake"
    mkdir -p "$build_dir"
    (
        cd "$build_dir"
        # System cmake (3.28 on Ubuntu 24.04) has no GNU flag mapping for
        # C++26, which this project requires — use the newer cmake pip
        # installs into the venv (see falcon-core-develop/requirements.txt).
        "$venv_cmake" .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=gcc-14 -DCMAKE_CXX_COMPILER=g++-14
        make -j"$(nproc)"
    )
    if [[ "$WITH_SYSTEM_DEPS" -eq 1 ]]; then
        sudo setcap 'cap_sys_nice=pe' "$build_dir/falcon/falcon" || \
            warn "setcap failed — falcon may not get real-time priority."
    else
        warn "Skipping setcap on falcon binary; re-run with --with-system-deps or run manually:"
        warn "  sudo setcap 'cap_sys_nice=pe' $build_dir/falcon/falcon"
    fi
}

# ---- main -------------------------------------------------------------------

should_run "root" && {
    log "Root: plotting/analysis venv"
    require_python "$PY312" && {
        if [[ -x "$ROOT/venv/bin/pip" && "$FORCE" -eq 0 ]]; then
            echo "  already exists, skipping (use --force to recreate)"
        else
            rm -rf "$ROOT/venv"
            "$PY312" -m venv "$ROOT/venv"
            "$ROOT/venv/bin/pip" install --upgrade pip --quiet
        fi
        "$ROOT/venv/bin/pip" install -r "$ROOT/requirements.txt"
    }
}

create_venv "zeromq_diy"           "zeromq_diy"           "venv" "$PY312"
create_venv "dareplane"            "dareplane"            "venv" "$PY312"
create_venv "falcon-core-develop"  "falcon-core-develop"  "venv" "$PY312"
create_venv "multiprocessing_diy"  "multiprocessing_diy"  "venv" "$PY312"
create_venv "bifrost"              "bifrost"              "venv" "$PY312" prepare_bifrost_vendor
create_venv "licorice"             "licorice"             "venv" "$PY38"
create_venv "brand-tutorial"       "brand-tutorial"       "rt"   "$PY38"

system_deps
build_zeromq_diy
build_dareplane
build_brand_tutorial
build_falcon

log "Done"
echo "Next: sudo -E python3 benchmark_all.py"
[[ "$WITH_BUILDS" -eq 1 ]] || echo "(native builds were skipped — re-run with --with-builds once system deps are in place)"
