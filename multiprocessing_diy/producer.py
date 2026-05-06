#!/usr/bin/env python3
"""Producer node that sends messages via Python multiprocessing IPC.

Minimal fast-path version: sends raw bytes over a Unix domain socket using
`multiprocessing.connection.Client`.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import statistics
import struct
import time
from multiprocessing.connection import Client


WARMUP_MESSAGES = 500


def _period_stats_us(times: list[float]) -> tuple[float, float, float, int]:
    """Return (mean_us, std_us, max_us, max_idx) for successive diffs."""
    if len(times) < 2:
        return (math.nan, math.nan, math.nan, -1)
    diffs = [b - a for a, b in zip(times, times[1:])]
    max_val = max(diffs)
    max_idx = diffs.index(max_val)
    mean_s = statistics.fmean(diffs)
    std_s = statistics.pstdev(diffs)
    return (mean_s * 1e6, std_s * 1e6, max_val * 1e6, max_idx)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_messages", type=int, default=3)
    parser.add_argument("--msg_size", type=int, default=1)
    parser.add_argument("--num_channels", type=int, default=1)
    parser.add_argument("--output_file", type=str, default="producer_metric.csv")
    parser.add_argument("--max_buffer_size", type=int, default=10)  # not used
    args = parser.parse_args()

    # Payload is a float64 array; first element carries the timestamp.
    n_f64 = int(args.num_channels) * int(args.msg_size)
    if n_f64 < 1:
        raise SystemExit("--num_channels * --msg_size must be >= 1")

    payload = bytearray(n_f64 * 8)
    payload_view = memoryview(payload)
    send_times: list[float] = []

    conn = None
    try:
        conn = Client(
            "/tmp/mp_comm.sock",
            family="AF_UNIX",
            authkey=b"benchmark",
        )

        # Warmup: stabilize the stream before measurements.
        for _ in range(WARMUP_MESSAGES):
            now = time.monotonic()
            struct.pack_into("d", payload, 0, now)
            conn.send_bytes(payload_view)

        for _ in range(args.n_messages):
            now = time.monotonic()
            struct.pack_into("d", payload, 0, now)
            conn.send_bytes(payload_view)
            send_times.append(now)

    except KeyboardInterrupt:
        print("\n\nShutting down producer...")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

        print(f"Total messages sent: {len(send_times)}")

        mean_us, std_us, max_us, max_idx = _period_stats_us(send_times)
        print(f"Average send period (us): {mean_us:.4f}")
        print(f"Max send period (us): {max_us:.4f}, idx: {max_idx}")
        print(f"Std send period (us): {std_us:.4f}")

        with open(args.output_file + "_Producer.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Send_period"])
            writer.writerow(["mean", f"{mean_us}"])
            writer.writerow(["std", f"{std_us}"])
            writer.writerow(["max", f"{max_us}"])

        diffs_path = args.output_file + "_send_times.csv"
        with open(diffs_path, "w", newline="") as f:
            if len(send_times) >= 2:
                for a, b in zip(send_times, send_times[1:]):
                    f.write(f"{b - a}\n")

        print("Producer stopped.")


if __name__ == "__main__":
    main()
