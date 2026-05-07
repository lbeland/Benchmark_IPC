import re
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


BASE_DIR = Path("./")
ZEROMQ_RESULTS = BASE_DIR / "zeromq_diy" / "rt_c_results"
FALCON_RESULTS = BASE_DIR / "falcon-core-develop" / "rt_c_results"

output_dir = os.path.join(BASE_DIR, "MA_results")

TARGET_MESSAGE_SIZE = 1
TARGET_CHANNELS = [1, 5, 20, 40]

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
        if channels not in TARGET_CHANNELS or msg_size != TARGET_MESSAGE_SIZE:
            continue

        data = np.atleast_1d(np.loadtxt(path, delimiter=","))
        series[channels] = data.astype(float) * 1e6  # seconds -> microseconds

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
    for channels in sorted(series):
        data_us = series[channels]
        if data_us.size == 0:
            continue

        color = colors[channels]
        indices = np.arange(data_us.size)

        ax_line.plot(
            indices,
            data_us,
            linewidth=1,
            color=color,
            alpha=0.9,
            label=channels
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
    ax.grid(True, which="major", alpha=0.7, linewidth=0.8)
    ax.grid(True, which="minor", alpha=0.5, linewidth=0.5)
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
    ax.grid(True, which="major", alpha=0.7, linewidth=0.8)
    ax.grid(True, which="minor", alpha=0.5, linewidth=0.5)
    # ax.spines["top"].set_visible(False)


def main() -> None:
    zeromq_series = load_latency_series(ZEROMQ_RESULTS)
    falcon_series = load_latency_series(FALCON_RESULTS)

    common_msg_sizes = sorted(set(zeromq_series) & set(falcon_series))
    if not common_msg_sizes:
        raise RuntimeError("No common message sizes found in the Zeromq and Falcon result folders.")

    # Restrict to message sizes available in both systems for fair visual comparison
    zeromq_series = {k: zeromq_series[k] for k in common_msg_sizes}
    falcon_series = {k: falcon_series[k] for k in common_msg_sizes}

    cmap = plt.get_cmap("Dark2")
    color_map = {
        channels: cmap(i)
        for i, channels in zip(np.linspace(0.12, 0.88, len(common_msg_sizes)), common_msg_sizes)
    }

    y_min, y_max = percentile_limits(zeromq_series, falcon_series, lower_pct=0.5, upper_pct=99.9, floor=0.1)

    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 10,
    })

    fig = plt.figure(figsize=(18, 6.8))
    grid = fig.add_gridspec(1, 4, width_ratios=[3.6, 1.5, 1.5, 3.6], wspace=0.05)

    ax_zero_line = fig.add_subplot(grid[0, 0])
    ax_zero_hist = fig.add_subplot(grid[0, 1], sharey=ax_zero_line)
    ax_falcon_hist = fig.add_subplot(grid[0, 2], sharey=ax_zero_line)
    ax_falcon_line = fig.add_subplot(grid[0, 3], sharey=ax_zero_line)

    add_series_to_axes(ax_zero_line, ax_zero_hist, zeromq_series, color_map, mirror_histogram=True)
    add_series_to_axes(ax_falcon_line, ax_falcon_hist, falcon_series, color_map, mirror_histogram=False)

    style_line_axis(ax_zero_line, "left", ylabel="Latency (μs)")
    style_hist_axis(ax_zero_hist, "right")
    style_hist_axis(ax_falcon_hist, "left")
    style_line_axis(ax_falcon_line, "right", ylabel="Latency (μs)")

    ax_zero_line.set_ylim(y_min, y_max)
    ax_zero_line.set_title("ZeroMQ")
    ax_falcon_line.set_title("Falcon")
    ax_zero_hist.set_title("Distribution")
    ax_falcon_hist.set_title("Distribution")

    ax_zero_hist.tick_params(labelleft=False, labelright=False)
    ax_falcon_hist.tick_params(labelright=False, labelleft=False)

    # Reduce clutter in the center
    ax_zero_hist.spines["left"].set_visible(False)
    ax_falcon_hist.spines["right"].set_visible(False)

    # Single shared legend above the plots
    handles, labels = ax_zero_line.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        title="Number of channels",
        loc="upper center",
        ncol=min(5, len(labels)),
        frameon=False,
        bbox_to_anchor=(0.5, 0.98),
    )

    # fig.text(0.25, 0.02, "Time series", ha="center", va="center", fontsize=10, alpha=0.85)
    # fig.text(0.75, 0.02, "Time series", ha="center", va="center", fontsize=10, alpha=0.85)

    plt.subplots_adjust(top=0.78, bottom=0.12, left=0.06, right=0.94)
    plt.savefig(os.path.join(output_dir, "latency_comparison.svg"), dpi=300)
    plt.show()


if __name__ == "__main__":
    main()