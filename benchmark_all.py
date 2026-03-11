#!/usr/bin/env python3
"""
Benchmark script for running IPC framework benchmarks.
"""
import os
import subprocess
import sys
import signal
from pathlib import Path
import time


# Configuration
N_MESSAGES = 1000
NUM_CHANNELS_LIST = [1, 5, 20, 40]
MSG_SIZES = [1, 128, 256, 512, 1024, 2048, 4096]
MAX_BUFFER = 10
OVERWRITE = False


def signal_handler(signum, frame):
    """Handle termination signals"""
    print(f"Received termination signal at channels={current_channels}, msg_size={current_msg_size}")
    sys.exit(1)


def run_benchmark(directory, venv_name, num_channels, msg_size):
    """
    Run benchmark in the specified directory with given parameters.
    """
    dir_path = Path(directory)
    venv_activate = f"{venv_name}/bin/activate"
    executables = []

    if os.path.exists(dir_path / "c_benchmark.py"):
        executables.append("c_benchmark.py")
    if os.path.exists(dir_path / "benchmark.py"):
        executables.append("benchmark.py")

    for exe in executables:
        # Build the command
        cmd = [
            "bash", "-c",
            f"cd {dir_path} && source {venv_activate} && "
            f"python3 {exe} --n_messages {N_MESSAGES} "
            f"--num_channels {num_channels} --msg_size {msg_size} "
            f"--max_buffer_size {MAX_BUFFER}"
        ]
        
        if OVERWRITE:
            cmd[2] += " --overwrite"
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=False)
            time.sleep(0.5)
        except subprocess.CalledProcessError as e:
            print(f"Error running benchmark: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error: {e}")
            continue


def main():
    """Main execution function"""
    global current_channels, current_msg_size
    
    # Set up signal handler
    signal.signal(signal.SIGTERM, signal_handler)
    
    for num_channels in NUM_CHANNELS_LIST:
        for msg_size in MSG_SIZES:
            current_channels = num_channels
            current_msg_size = msg_size
            
            # print(f"Running benchmarks Bifrost: channels={num_channels}, msg_size={msg_size}")
            # run_benchmark("./bifrost", "venv", num_channels, msg_size)
            
            # print(f"Running benchmarks Zeromq_diy: channels={num_channels}, msg_size={msg_size}")
            # run_benchmark("./zeromq_diy", "venv", num_channels, msg_size)
            
            print(f"Running benchmarks Dareplane: channels={num_channels}, msg_size={msg_size}")
            run_benchmark("./dareplane", "venv", num_channels, msg_size)
            
            # print(f"Running benchmarks Brand-tutorial: channels={num_channels}, msg_size={msg_size}")
            # run_benchmark("./brand-tutorial", "rt", num_channels, msg_size)
            
            # print(f"Running benchmarks Falcon: channels={num_channels}, msg_size={msg_size}")
            # run_benchmark("./falcon-core-develop", "venv", num_channels, msg_size)


if __name__ == "__main__":
    current_channels = None
    current_msg_size = None
    main()
