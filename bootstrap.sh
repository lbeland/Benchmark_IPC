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
    local name="$1" dir="$2" venv_name="$3" py="$4"
    should_run "$name" || return 0
    require_python "$py" || return 0

    log "$name: venv ($venv_name, $py)"
    local venv_path="$ROOT/$dir/$venv_name"

    if [[ -d "$venv_path" && "$FORCE" -eq 0 ]]; then
        echo "  already exists, skipping (use --force to recreate)"
    else
        rm -rf "$venv_path"
        "$py" -m venv "$venv_path"
        "$venv_path/bin/pip" install --upgrade pip --quiet
    fi

    local req="$ROOT/$dir/requirements.txt"
    if [[ -f "$req" ]]; then
        "$venv_path/bin/pip" install -r "$req"
    else
        echo "  no requirements.txt in $dir, skipping pip install"
    fi
}

# ---- system packages (only with --with-system-deps) -----------------------

system_deps() {
    should_run "system-deps" || return 0
    [[ "$WITH_SYSTEM_DEPS" -eq 1 ]] || {
        warn "Skipping system packages. zeromq_diy/falcon need: libzmq3-dev, gcc-14, g++-14."
        warn "Re-run with --with-system-deps to install them via apt (requires sudo)."
        return 0
    }
    log "system packages (apt)"
    sudo apt-get update
    sudo apt-get install -y libzmq3-dev gcc-14 g++-14
}

# ---- native builds (only with --with-builds) -------------------------------

build_zeromq_diy() {
    should_run "zeromq_diy" || return 0
    [[ "$WITH_BUILDS" -eq 1 ]] || return 0
    log "zeromq_diy: make"
    make -C "$ROOT/zeromq_diy"
}

build_dareplane() {
    should_run "dareplane" || return 0
    [[ "$WITH_BUILDS" -eq 1 ]] || return 0
    log "dareplane: make (recursive, builds c-producer/c-consumer)"
    make -C "$ROOT/dareplane"
}

build_falcon() {
    should_run "falcon-core-develop" || return 0
    [[ "$WITH_BUILDS" -eq 1 ]] || return 0
    log "falcon-core-develop: cmake + make"
    local build_dir="$ROOT/falcon-core-develop/build"
    mkdir -p "$build_dir"
    (
        cd "$build_dir"
        cmake .. -DCMAKE_BUILD_TYPE=Debug
        make
    )
    if [[ "$WITH_SYSTEM_DEPS" -eq 1 ]]; then
        sudo setcap 'cap_sys_nice=pe' "$build_dir/falcon/falcon" || \
            warn "setcap failed — falcon may not get real-time priority."
    else
        warn "Skipping setcap on falcon binary; re-run with --with-system-deps or run manually:"
        warn "  sudo setcap 'cap_sys_nice=pe' $build_dir/falcon/falcon"
    fi
}

build_bifrost() {
    should_run "bifrost" || return 0
    [[ "$WITH_BUILDS" -eq 1 ]] || return 0
    warn "bifrost needs a CUDA toolchain and a long ./configure && make build."
    warn "Not automated here — build it manually inside bifrost/ if you need the C/CUDA benchmark path."
}

# ---- main -------------------------------------------------------------------

should_run "root" && {
    log "Root: plotting/analysis venv"
    require_python "$PY312" && {
        if [[ -d "$ROOT/venv" && "$FORCE" -eq 0 ]]; then
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
create_venv "bifrost"              "bifrost"              "venv" "$PY312"
create_venv "brand-tutorial"       "brand-tutorial"       "rt"   "$PY38"

system_deps
build_zeromq_diy
build_dareplane
build_falcon
build_bifrost

log "Done"
echo "Next: sudo -E python3 benchmark_all.py"
[[ "$WITH_BUILDS" -eq 1 ]] || echo "(native builds were skipped — re-run with --with-builds once system deps are in place)"
