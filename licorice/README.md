# licorice — not currently in the active benchmark comparison

Origin: https://github.com/bil/licorice

[LiCoRICE](https://github.com/bil/licorice) is a tick-scheduled real-time
framework: you define "modules" (written in Python or C) in a YAML model,
and `licorice go <model>` code-generates each module into Cython/C, compiles
it, and runs every module as its own OS process, communicating through
POSIX shared memory + semaphores.

**Why it's excluded from the comparison:** LiCoRICE's `timer` process
enforces a *hard* per-tick deadline — every module must finish its per-tick
work within `tick_len` microseconds, or the entire run is aborted on the
first miss (`timer.c.j2`, `sem_trywait` check, no tolerance, not
configurable). At this benchmark's tight default (`t_wait=0.001s` = 1ms),
a Python/Cython-interpreted module's overhead makes surviving *every single
one* of 10,000+ ticks without a single miss infeasible — confirmed upstream
by their own examples, which use `tick_len` of 10ms–100ms for
Python-language modules, 2–3 orders of magnitude looser than what's used
here. A raw C-language module could plausibly survive the tight timing, but
C-language module support turned out to be unimplemented in this LiCoRICE
release (v0.0.7): `module.c.j2` (the C module template) has none of the
shared-memory/semaphore runtime code that `module.pyx.j2` has for Python,
none of the shipped examples use `language: c`, and the scaffold generator
files `template_funcs.py` references for it don't exist in
`licorice/generators/`.

The working (but unused) Python producer/consumer harness is still here —
`benchmark.py`, `producer.py`, `producer_constructor.py`, `consumer.py`,
`consumer_constructor.py` — in case a future version of LiCoRICE fixes C
support, or this benchmark's timing requirements loosen. It correctly
compiles and runs; it just gets killed by the tick deadline before
producing results at this benchmark's default timing.

This is a fresh full clone of upstream (not a stripped submodule like the
other frameworks here), since LiCoRICE needs its own source tree
(`licorice/`, `install/`, templates, etc.) to compile models. One local
patch was needed to get it running at all on a system with multiple Python
versions installed side by side: `licorice/template_funcs.py` queried the
unversioned `python3-config` for link flags, which resolves to whatever
`python3-config` happens to symlink to system-wide (Python 3.12 here) — not
necessarily the Python actually running LiCoRICE (3.8 in our venv) — causing
generated modules to compile against 3.8 headers but link against 3.12's
libpython. Patched to use the versioned `python{major}.{minor}-config`
matching the running interpreter.
