import subprocess
import time
import os
import signal
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_messages", type=int, default=10000)
    parser.add_argument("--msg_size", type=int, default=1)
    parser.add_argument("--num_channels", type=int, default=1)
    parser.add_argument("--max_buffer_size", type=int, default=16)
    parser.add_argument("--t_wait", type=float, default=0.0001)
    parser.add_argument("--output_file", type=str, default="Producer.csv")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result_folder = f"{REPO_ROOT}/rt_results"

    os.makedirs(result_folder, exist_ok=True)

    if os.path.exists(f"{result_folder}/{args.num_channels}_{args.msg_size}_Consumer.csv") and not args.overwrite:
        return  # Skip if already exists

    os.remove("/tmp/zeromq_comm.sock") if os.path.exists("/tmp/zeromq_comm.sock") else None

    # 1. Start consumer FIRST
    consumer = subprocess.Popen(
        [
            "sudo", "chrt", "-f", "99",
            "taskset", "-c", "5",
            f"{REPO_ROOT}/venv/bin/python3",
            f"{REPO_ROOT}/consumer.py",
            "--n_messages",  str(args.n_messages),
            "--output_file", f"{result_folder}/{args.num_channels}_{args.msg_size}"
        ],
        preexec_fn=os.setsid,  # allows group kill
    )

    # Give consumer time to bind socket
    time.sleep(0.5)

    # 2. Start producer
    producer = subprocess.Popen(
        [
            "sudo", "chrt", "-f", "99",
            "taskset", "-c", "6",
            f"{REPO_ROOT}/venv/bin/python3",
            f"{REPO_ROOT}/producer.py",
            "--n_messages", str(args.n_messages),
            "--num_channels", str(args.num_channels),
            "--msg_size", str(args.msg_size),
            "--max_buffer_size", str(args.max_buffer_size),
            "--t_wait", str(args.t_wait),
            "--output_file", f"{result_folder}/{args.num_channels}_{args.msg_size}"
        ],
        preexec_fn=os.setsid,
    )

    try:
        # 3. Wait for completion
        producer.wait(args.t_wait * args.n_messages * 2)  # generous timeout
        consumer.wait(args.t_wait * args.n_messages * 2)
    except KeyboardInterrupt:
        terminate(producer)
        terminate(consumer)

    except subprocess.TimeoutExpired:
        print("Timeout expired, terminating processes")
        terminate(producer)
        terminate(consumer)
        raise

    print(f"Benchmark complete")


def terminate(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass


if __name__ == "__main__":
    # RT scheduling removed from parent - let producer/consumer set their own if needed
    main()
