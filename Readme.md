# Benchmark IPC

Benchmarks the inter-process communication (IPC) performance of several
real-time / neuroscience data-acquisition frameworks against each other,
using the same producer → consumer pipeline shape (one process emits
timestamped messages, another receives and times them) across a range of
channel counts and message sizes.

## Use case

Each framework below wraps the same benchmark: a **producer** emits
`--n_messages` messages of `--num_channels` × `--msg_size` doubles at a
configurable rate (`--t_wait` seconds between sends), and a **consumer**
times how long each message takes to arrive. This lets you compare
send/receive jitter and throughput across frameworks that are otherwise
built very differently (ring buffers, ZeroMQ sockets, Redis streams, shared
memory, plain multiprocessing, ...) under identical conditions.

## Frameworks benchmarked

| Framework | Origin |
|---|---|
| [bifrost](bifrost/README.md) | https://github.com/lwa-project/bifrost |
| [brand-tutorial](brand-tutorial/README.md) | https://github.com/brandbci/brand-tutorial |
| [dareplane](dareplane/README.md) | https://github.com/bsdlab/Dareplane |
| [falcon-core-develop](falcon-core-develop/README.md) | https://github.com/falcon-eyrie/falcon-core |
| [licorice](licorice/README.md) | https://github.com/bil/licorice (not currently in the active comparison — see its README) |
| [zeromq_diy](zeromq_diy/Readme.md) | self-made, ZeroMQ-based reference implementation |
| multiprocessing_diy | self-made, Python `multiprocessing`-based reference implementation |

Each subfolder is its own git submodule (except `multiprocessing_diy`, which
lives directly in this repo) pinned to a specific upstream commit — see each
one's own README for exactly what was changed to add the benchmark harness.

## Installation

Each framework gets its own venv (they need different Python versions and
mutually incompatible package pins) and, optionally, its native build step:

```bash
./bootstrap.sh --with-builds --with-system-deps
```

- `--with-builds` also compiles native components (C/C++ producers/consumers,
  falcon, redis-server, ...). Skip it if you only need the pure-Python paths.
- `--with-system-deps` installs the apt packages those builds need
  (`libzmq3-dev`, `gcc-14`, `g++-14`, ...). Requires `sudo`.
- `--only NAME` bootstraps a single framework, e.g. `--only falcon-core-develop`.
- `--force` recreates a venv that already exists.

See `./bootstrap.sh --help` for the full list of flags.

## Running benchmarks

Run every framework across the full sweep of channel counts and message
sizes configured in `benchmark_all.py`:

```bash
sudo -E python3 benchmark_all.py
```

`sudo` is needed so the producer/consumer subprocesses can run at real-time
scheduling priority (99). Use `--overwrite` if the script has already run
and you want to replace existing results (edit `OVERWRITE` in
`benchmark_all.py`, or pass it through when running a single framework
directly — see each framework's own README).

To benchmark a single framework directly instead, `cd` into its folder and
run its `benchmark.py` (pure Python) or `c_benchmark.py` (native/C) —
the exact command and arguments are documented in that framework's README.

## Plotting results

```bash
python3 plot_benchmark_throughput.py
python3 plot_latency_comparison.py
```

Results are read from each framework's `rt_results/`/`rt_c_results/`
folders. These are named for the real-time kernel this was originally
benchmarked under — if your system isn't running an RT kernel, the naming
doesn't matter functionally, just ignore it.
