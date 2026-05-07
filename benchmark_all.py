#!/usr/bin/env python3
import os
import subprocess
import sys
import signal
from pathlib import Path
import time

# Configuration
N_MESSAGES = 10000
NUM_CHANNELS_LIST = [1, 5, 20, 40]
MSG_SIZES = [1, 128, 256, 512, 1024, 2048, 4096]
MAX_BUFFER = 16
T_WAIT = 0.0001
OVERWRITE = True

current_channels = None
current_msg_size = None
active_proc = None


def terminate_process_group(proc, graceful_signal=signal.SIGINT, timeout=5):
    """Terminate a subprocess and its whole process group."""
    if proc is None:
        return

    if proc.poll() is not None:
        return

    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return

    try:
        os.killpg(pgid, graceful_signal)
    except ProcessLookupError:
        return

    try:
        proc.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def signal_handler(signum, frame):
    """Handle termination signals in the parent."""
    global active_proc
    print(
        f"\nReceived signal {signum} at channels={current_channels}, "
        f"msg_size={current_msg_size}"
    )
    terminate_process_group(active_proc, graceful_signal=signal.SIGINT, timeout=5)
    sys.exit(128 + signum)


def run_benchmark(directory, venv_name, num_channels, msg_size):
    global active_proc

    dir_path = Path(directory)
    python_bin = dir_path / f"{venv_name}/bin/python3"
    executables = []

    if (dir_path / "c_benchmark.py").exists():
        executables.append(dir_path / "c_benchmark.py")
    # if (dir_path / "benchmark.py").exists():
    #     executables.append(dir_path / "benchmark.py")

    for exe in executables:
        cmd = [
            str(python_bin),
            str(exe),
            "--n_messages", str(N_MESSAGES),
            "--num_channels", str(num_channels),
            "--msg_size", str(msg_size),
            "--max_buffer_size", str(MAX_BUFFER),
            "--t_wait", str(T_WAIT),
        ]

        if OVERWRITE:
            cmd.append("--overwrite")

        print(cmd)

        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                preexec_fn=os.setsid,  # new process group
            )
            active_proc = proc

            returncode = proc.wait()

            if returncode != 0:
                print(f"Benchmark exited with code {returncode}: {exe}")

            time.sleep(0.5)

        except KeyboardInterrupt:
            print(
                f"\nKeyboardInterrupt during channels={num_channels}, "
                f"msg_size={msg_size}"
            )
            terminate_process_group(proc, graceful_signal=signal.SIGINT, timeout=5)
            raise

        except Exception as e:
            print(f"Unexpected error while running {exe}: {e}")
            terminate_process_group(proc, graceful_signal=signal.SIGTERM, timeout=5)
            continue

        finally:
            active_proc = None


def main():
    global current_channels, current_msg_size

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        for num_channels in NUM_CHANNELS_LIST:
            for msg_size in MSG_SIZES:
                current_channels = num_channels
                current_msg_size = msg_size

                # print(f"Running benchmarks Dareplane: "f"channels={num_channels}, msg_size={msg_size}")
                # run_benchmark("./dareplane", "venv", num_channels, msg_size)

                # print(f"Running benchmarks Bifrost: channels={num_channels}, msg_size={msg_size}")
                # run_benchmark("./bifrost", "venv", num_channels, msg_size)

                print(f"Running benchmarks Zeromq_diy: channels={num_channels}, msg_size={msg_size}")
                run_benchmark("./zeromq_diy", "venv", num_channels, msg_size)

                # print(f"Running benchmarks Brand-tutorial: channels={num_channels}, msg_size={msg_size}")
                # run_benchmark("./brand-tutorial", "rt", num_channels, msg_size)

                # print(f"Running benchmarks Falcon: channels={num_channels}, msg_size={msg_size}")
                # run_benchmark("./falcon-core-develop", "venv", num_channels, msg_size)

                # print(f"Running benchmarks Multiprocessing: channels={num_channels}, msg_size={msg_size}")
                # run_benchmark("./multiprocessing_diy", "venv", num_channels, msg_size)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
