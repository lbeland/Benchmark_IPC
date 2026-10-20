import argparse
import re
import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


mpl.rcParams.update({
    # "font.size": 6,
    "pgf.texsystem": "pdflatex",
    'font.family': 'serif',
    'text.usetex': True,
    'pgf.rcfonts': False,
})


PLOTS_DIR = "/home/linda/Documents/MA/plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

TEXTWIDTH    = 6.30045
ASPECT_RATIO = 9/16
SCALE        = 1.0
FIG_WIDTH    = TEXTWIDTH * SCALE
FIG_HEIGHT   = FIG_WIDTH * ASPECT_RATIO
FIGSIZE      = (FIG_WIDTH, FIG_HEIGHT)


def save_pgf(fig, name: str) -> None:
    fig.savefig(os.path.join(PLOTS_DIR, f"{name}.pgf"), bbox_inches="tight")

def save_png(fig, name: str) -> None:
    fig.savefig(os.path.join(PLOTS_DIR, f"{name}.png"), bbox_inches="tight", dpi=300)

def save_svg(fig, name: str) -> None:
    fig.savefig(os.path.join(PLOTS_DIR, f"{name}.svg"), bbox_inches="tight")


def format_payload(x):
    r"""Binary size label: "8 B" / "16 KiB" / "1.25 MiB" (base 1024).
    Sub-unit values keep up to two decimals, trailing zeros stripped."""
    x = int(x)
    for unit, factor in (("MiB", 1024 ** 2), ("KiB", 1024)):
        if x >= factor:
            s = f"{x / factor:.2f}".rstrip("0").rstrip(".")
            return f"{s} {unit}"
    return f"{x} B"


BASE_DIR = Path("./")
ZEROMQ_RESULTS = BASE_DIR / "zeromq_diy" / "rt_c_results"
FALCON_RESULTS = BASE_DIR / "falcon-core-develop" / "rt_c_results"
MULTIPROCESSING_RESULTS = BASE_DIR / "multiprocessing_diy" / "rt_results"

# Left-hand panel is selectable from the CLI; Falcon is always on the right.
# Maps the CLI keyword -> (display label, results directory).
LEFT_CHOICES = {
    "zeromq": ("ZeroMQ", ZEROMQ_RESULTS),
    "multiprocessing": ("Multiprocessing", MULTIPROCESSING_RESULTS),
}

output_dir = os.path.join(BASE_DIR, "MA_results")

# Match the payloads shown in the jitter table (create_latex in
# plot_benchmark_throughput.py). That script filters on
# total_size = num_channels * msg_size * 8  (float64 bytes) and targets
# [8, 1024, 16*1024, 1280*1024]. Here the filter is applied to
# num_channels * msg_size (before the *8), so divide those by 8.
TARGET_TOTAL_SIZES = [8, 1024, 4 * 1024, 32*1024,  1280 * 1024]
TARGET_PAYLOADS = [s // 8 for s in TARGET_TOTAL_SIZES]  # [1, 128, 2048, 163840]

# TARGET_MESSAGE_SIZE = 256
# TARGET_CHANNELS = [1, 5, 20, 40]

FILE_PATTERN = re.compile(r"^(?P<channels>\d+)_(?P<msg_size>\d+)_process_times\.csv$")


def load_latency_series(results_dir: Path) -> dict[int, np.ndarray]:
    series: dict[int, np.ndarray] = {}

    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory does not exist: {results_dir}")

    for path in sorted(results_dir.iterdir()):
        if not path.is_file():
            continue

        match = FILE_PATTERN.match(path.name)
        if match is None:
            continue

        channels = int(match.group("channels"))
        msg_size = int(match.group("msg_size"))
        payload = channels * msg_size # bytes per message
        if payload not in TARGET_PAYLOADS:
            continue

        data = np.atleast_1d(np.loadtxt(path, delimiter=","))
        series[payload*8] = data.astype(float) * 1e6  # seconds -> microseconds

    return series


def percentile_limits(
    *series_dicts: dict[int, np.ndarray],
    lower_pct: float = 1.0,
    upper_pct: float = 99.5,
    floor: float = 0.1,
) -> tuple[float, float]:
    all_values = []
    for series in series_dicts:
        for values in series.values():
            if values.size:
                all_values.append(values)

    if not all_values:
        return floor, 1000.0

    values = np.concatenate(all_values)
    values = values[np.isfinite(values) & (values > 0)]
    if values.size == 0:
        return floor, 1000.0

    lo = min(values)   #max(np.percentile(values, lower_pct), floor)
    hi = max(values)   #max(np.percentile(values, upper_pct), lo * 1.2)
    return lo, hi


def add_series_to_axes(
    ax_line: plt.Axes,
    ax_hist: plt.Axes,
    series: dict[int, np.ndarray],
    colors: dict[int, tuple[float, float, float, float]],
    mirror_histogram: bool = False,
) -> None:
    for payload in sorted(series):
        data_us = series[payload]
        if data_us.size == 0:
            continue

        color = colors[payload]
        indices = np.arange(data_us.size)

        ax_line.plot(
            indices,
            data_us,
            linewidth=1,
            color=color,
            alpha=0.8,
            label=format_payload(payload),
        )

        positive = data_us[data_us > 0]
        if positive.size == 0:
            continue

        lower = max(float(positive.min()), 0.1)
        upper = max(float(positive.max()), lower * 1.05)
        bins = np.logspace(np.log10(lower), np.log10(upper), 28)

        ax_hist.hist(
            positive,
            bins=bins,
            histtype="stepfilled",
            orientation="horizontal",
            color=color,
            alpha=0.18,
            edgecolor=color,
            linewidth=1.0,
        )
        ax_hist.hist(
            positive,
            bins=bins,
            histtype="step",
            orientation="horizontal",
            color=color,
            linewidth=1.0,
        )

    if mirror_histogram:
        ax_hist.invert_xaxis()


def style_line_axis(ax: plt.Axes, side: str, ylabel: str | None = None) -> None:
    if side == "left":
        ax.yaxis.tick_left()
        ax.yaxis.set_label_position("left")
        ax.spines["right"].set_visible(False)
    elif side == "right":
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.spines["left"].set_visible(False)
    else:
        raise ValueError(f"Unsupported axis side: {side}")

    if ylabel:
        ax.set_ylabel(ylabel)

    ax.set_xlabel("Message index")
    ax.set_yscale("log")
    ax.grid(True, axis="y", which="major", alpha=0.7, linewidth=0.8)
    ax.grid(True, axis="y", which="minor", alpha=0.7, linewidth=0.8)
    # ax.spines["top"].set_visible(False)


def style_hist_axis(ax: plt.Axes, side: str, xlabel: str = "Count") -> None:
    if side == "left":
        ax.yaxis.tick_left()
        ax.yaxis.set_label_position("left")
        ax.spines["right"].set_visible(False)
    elif side == "right":
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.spines["left"].set_visible(False)
    else:
        raise ValueError(f"Unsupported axis side: {side}")

    ax.set_xlabel(xlabel)
    ax.set_yscale("log")
    # ax.grid(True, axis="x", alpha=0.22, linewidth=0.8)
    ax.grid(True, axis="y", which="major", alpha=0.7, linewidth=0.8)
    ax.grid(True, axis="y", which="minor", alpha=0.7, linewidth=0.8)
    # ax.spines["top"].set_visible(False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot per-message latency with a selectable system on the "
                    "left panel; Falcon is always on the right panel."
    )
    parser.add_argument(
        "left",
        nargs="?",
        choices=sorted(LEFT_CHOICES),
        default="zeromq",
        help="System to show on the left panel (default: zeromq). "
             "Falcon is always the right panel.",
    )
    args = parser.parse_args()

    left_label, left_dir = LEFT_CHOICES[args.left]

    left_series = load_latency_series(left_dir)
    falcon_series = load_latency_series(FALCON_RESULTS)

    common_msg_sizes = sorted(set(left_series) & set(falcon_series))
    if not common_msg_sizes:
        raise RuntimeError(
            f"No common message sizes found in the {left_label} and Falcon result folders."
        )

    # Restrict to message sizes available in both systems for fair visual comparison
    left_series = {k: left_series[k] for k in common_msg_sizes}
    falcon_series = {k: falcon_series[k] for k in common_msg_sizes}

    # Default matplotlib property-cycle colors (C0, C1, ...).
    color_map = {
        payload: f"C{i}"
        for i, payload in enumerate(common_msg_sizes)
    }

    y_min, y_max = percentile_limits(left_series, falcon_series, lower_pct=0.5, upper_pct=99.9, floor=0.1)

    fig = plt.figure(figsize=FIGSIZE, layout="constrained")
    grid = fig.add_gridspec(1, 4, width_ratios=[3.6, 1.5, 1.5, 3.6], wspace=0.05)

    ax_left_line = fig.add_subplot(grid[0, 0])
    ax_left_hist = fig.add_subplot(grid[0, 1], sharey=ax_left_line)
    ax_falcon_hist = fig.add_subplot(grid[0, 2], sharey=ax_left_line)
    ax_falcon_line = fig.add_subplot(grid[0, 3], sharey=ax_left_line)

    add_series_to_axes(ax_left_line, ax_left_hist, left_series, color_map, mirror_histogram=True)
    add_series_to_axes(ax_falcon_line, ax_falcon_hist, falcon_series, color_map, mirror_histogram=False)

    style_line_axis(ax_left_line, "left", ylabel=r"Latency [$\mu$s]")
    style_hist_axis(ax_left_hist, "right")
    style_hist_axis(ax_falcon_hist, "left")
    style_line_axis(ax_falcon_line, "right", ylabel=r"Latency [$\mu$s]")

    ax_left_line.set_ylim(y_min, y_max)
    ax_left_line.set_title(f"(a) {left_label}")
    ax_falcon_line.set_title("(b) Falcon")

    # Put both histogram count axes on the same scale. sharex can't be used
    # here because the left panel is mirrored (inverted x), so match the
    # limits by magnitude: left runs cmax -> 0, Falcon runs 0 -> cmax.
    cmax = max(
        max(abs(v) for v in ax_left_hist.get_xlim()),
        max(abs(v) for v in ax_falcon_hist.get_xlim()),
    )
    ax_left_hist.set_xlim(cmax, 0)
    ax_falcon_hist.set_xlim(0, cmax)

    ax_left_hist.tick_params(axis="y", which="both", labelleft=False, labelright=False, left=False, right=False)
    ax_falcon_hist.tick_params(axis="y", which="both", labelleft=False, labelright=False, left=False, right=False)


    # Reduce clutter in the center
    ax_left_hist.spines["left"].set_visible(False)
    ax_falcon_hist.spines["right"].set_visible(False)

    # Single shared legend below the plots. "outside lower center" makes
    # constrained_layout reserve space for it instead of overlapping the axes.
    handles, labels = ax_left_line.get_legend_handles_labels()
    leg = fig.legend(
        handles,
        labels,
        title="Payload size",
        loc="outside lower center",
        ncol=min(5, len(labels)),
        frameon=True,
        handlelength=2.5,
    )
    # Thicken the colour swatches in the legend without touching the plotted
    # lines (which stay thin so the time series remain readable).
    for line in leg.get_lines():
        line.set_linewidth(2.0)

    fig_name = f"latency_comparison_{args.left}_vs_falcon"
    save_pgf(fig, fig_name)
    save_svg(fig, fig_name)
    save_png(fig, fig_name)
    plt.show()


if __name__ == "__main__":
    main()