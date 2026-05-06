#!/usr/bin/env python3
"""Consumer node that receives messages via Python multiprocessing IPC.

Minimal fast-path version: receives raw bytes over a Unix domain socket using
`multiprocessing.connection.Listener`.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import statistics
import struct
import time
from multiprocessing.connection import Listener


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


def _latency_stats_us(latencies_s: list[float]) -> tuple[float, float, float, int]:
    if len(latencies_s) == 0:
        return (math.nan, math.nan, math.nan, -1)
    max_val = max(latencies_s)
    max_idx = latencies_s.index(max_val)
    mean_s = statistics.fmean(latencies_s)
    std_s = statistics.pstdev(latencies_s)
    return (mean_s * 1e6, std_s * 1e6, max_val * 1e6, max_idx)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_messages", type=int, default=3)
    parser.add_argument("--output_file", type=str, default="recv_times.csv")
    args = parser.parse_args()

    address = "/tmp/mp_comm.sock"

    # Ensure old AF_UNIX socket path is removed (Listener won't overwrite).
    try:
        if os.path.exists(address):
            os.unlink(address)
    except OSError:
        pass

    recv_times: list[float] = []
    process_times: list[float] = []
    first_timestamp: float | None = None

    listener = Listener(
        address,
        family="AF_UNIX",
        authkey=b"benchmark",
    )

    try:
        conn = listener.accept()
        try:
            # Warmup: discard initial messages before measuring.
            for _ in range(WARMUP_MESSAGES):
                conn.recv_bytes()

            for counter in range(args.n_messages):
                data = conn.recv_bytes()
                now = time.monotonic()

                # Payload is a float64 array; first element is timestamp.
                timestamp = struct.unpack_from("d", data, 0)[0]
                if counter == 0:
                    first_timestamp = timestamp

                recv_times.append(now)
                process_times.append(now - timestamp)

        finally:
            try:
                conn.close()
            except Exception:
                pass

    except KeyboardInterrupt:
        print("\n\nShutting down consumer...")
    finally:
        try:
            listener.close()
        except Exception:
            pass

        print(f"Total messages processed: {len(process_times)}")

        mean_recv_us, std_recv_us, max_recv_us, max_recv_idx = _period_stats_us(
            recv_times
        )
        print(f"Average receive period (us): {mean_recv_us:.4f}")
        print(f"Max receive period (us): {max_recv_us:.4f}, idx: {max_recv_idx}")
        print(f"Std receive period (us): {std_recv_us:.4f}")

        mean_lat_us, std_lat_us, max_lat_us, max_lat_idx = _latency_stats_us(
            process_times
        )
        print(f"Average latency (us): {mean_lat_us:.4f}")
        print(f"Max latency (us): {max_lat_us:.4f}, idx: {max_lat_idx}")
        print(f"Std latency (us): {std_lat_us:.4f}")

        if len(recv_times) > 0 and first_timestamp is not None:
            throughput = args.n_messages / (recv_times[-1] - first_timestamp) / 1e3
            print(
                f"Started sending at {first_timestamp:.4f}, finished at {recv_times[-1]:.4f}"
            )
            print(
                "Throughput (msg/ms): "
                f"{args.n_messages}/{(recv_times[-1] - first_timestamp) * 1e3:.4f}ms="
                f"{throughput:.2f}"
            )
        else:
            throughput = float("nan")

        with open(args.output_file + "_Consumer.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Recv_period", "Latency", "Throughput"])
            writer.writerow(["mean", f"{mean_recv_us}", f"{mean_lat_us}", f"{throughput}"])
            writer.writerow(["std", f"{std_recv_us}", f"{std_lat_us}", ""])
            writer.writerow(["max", f"{max_recv_us}", f"{max_lat_us}", ""])

        with open(args.output_file + "_recv_times.csv", "w", newline="") as f:
            if len(recv_times) >= 2:
                for a, b in zip(recv_times, recv_times[1:]):
                    f.write(f"{b - a}\n")

        with open(args.output_file + "_process_times.csv", "w", newline="") as f:
            for v in process_times:
                f.write(f"{v}\n")

        print("Consumer stopped.")


if __name__ == "__main__":
    main()
