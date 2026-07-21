import argparse
import os
import subprocess
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_BIN = REPO_ROOT / "venv" / "bin"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_messages", type=int, default=1000)
    parser.add_argument("--msg_size", type=int, default=3)
    parser.add_argument("--num_channels", type=int, default=2)
    parser.add_argument("--max_buffer_size", type=int, default=10)  # not used
    parser.add_argument("--t_wait", type=float, default=0.0001)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output_file", type=str, default="send_times.csv")
    args = parser.parse_args()

    results_folder = REPO_ROOT / "rt_results"
    results_folder.mkdir(exist_ok=True)

    output_path = results_folder / f"{args.num_channels}_{args.msg_size}"
    if os.path.exists(f"{output_path}_Consumer.csv") and not args.overwrite:
        return  # Skip if already exists

    tick_len_us = max(1, round(args.t_wait * 1e6))

    model = {
        "config": {
            "tick_len": tick_len_us,
            "num_ticks": args.n_messages,
            "source_init_ticks": 500,
            "output_file": str(output_path),
        },
        "signals": {
            "message": {
                # A flat shape, not (num_channels, msg_size): LiCoRICE
                # squeezes any size-1 dimension out of a declared shape, so
                # a 2D shape's rank becomes unpredictable whenever
                # num_channels or msg_size is 1. producer.py/consumer.py
                # write/read via `[...]`/`.flat[0]`, which work regardless
                # of the resulting ndim (including the 0-d case when the
                # flat size itself is 1).
                "shape": f"({args.num_channels * args.msg_size},)",
                "dtype": "double",
            },
        },
        "modules": {
            "producer": {
                "language": "python",
                "constructor": True,
                "out": ["message"],
            },
            "consumer": {
                "language": "python",
                "constructor": True,
                "in": ["message"],
            },
        },
    }

    with open(REPO_ROOT / "benchmark.yaml", "w") as f:
        yaml.safe_dump(model, f, sort_keys=False)

    env = os.environ.copy()
    env["LICORICE_WORKING_PATH"] = str(REPO_ROOT)
    env["PATH"] = f"{VENV_BIN}:{env.get('PATH', '')}"

    proc = subprocess.run(
        ["sudo", "-E", "env", f"PATH={env['PATH']}", str(VENV_BIN / "licorice"), "go", "benchmark", "-y"],
        cwd=str(REPO_ROOT),
        env=env,
    )
    print(f"Benchmark complete (exit code {proc.returncode})")


if __name__ == "__main__":
    main()
