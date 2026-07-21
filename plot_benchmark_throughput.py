import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import LogNorm, LinearSegmentedColormap
import re

BASE_DIR = "./"
output_dir = os.path.join(BASE_DIR, "MA_results")
SUBFOLDERS = ["dareplane", "bifrost", "brand-tutorial", "multiprocessing_diy", "zeromq_diy", "falcon-core-develop", ]
# SUBFOLDERS = ["zeromq_diy", "falcon-core-develop"]

data_records = []

# Updated pattern to match: num_channels_msg_size_[Consumer|Producer].csv
pattern = re.compile(r"(\d+)_(\d+)_(Consumer|Producer).csv")

cmap = plt.get_cmap("Dark2")
SYSTEM_COLORS = {
    system: cmap(i)
    for i, system in zip(np.linspace(0.12, 0.88, len(SUBFOLDERS)), SUBFOLDERS)
}

SYSTEM_LABELS = {
    "bifrost": "Bifrost (Shared Memory)",
    "dareplane": "Dareplane (LSL-Streams)",
    "brand-tutorial": "BRAND (Redis)",
    "zeromq_diy": "ZeroMQ",
    "falcon-core-develop": "Falcon (Disruptor Buffer)",
    "multiprocessing_diy": "Multiprocessing"
}

def mad(data, axis=None):
    """Mean absolute deviation"""
    return np.mean(np.abs(data - np.mean(data, axis)), axis)

def format_payload(x):
    if x >= 1024:
        return f"{x/1024:.0f} KB"
    return f"{x} B"

TARGET_PAYLOADS = [8, 1024, 16 * 1024, 1280 * 1024]  # 8 B, 1 KB, 16 KB, 1280 KB

def create_latex(df_all):
    df_latency = df_all[df_all["metric"] == "latency"].copy()
    df_latency = df_latency[df_latency["total_size"].isin(TARGET_PAYLOADS)]

    # format cell contents
    df_latency["cell"] = df_latency.apply(
        lambda r: f"{r['std']/1000:.3f}",   #{r['mean']/1000:.2f} $\\pm$
        axis=1
    )

    # optional: prettier implementation labels
    impl_labels = {"Python": "Python","C": "C/C++"}
    df_latency["implementation_label"] = (
        df_latency["implementation"].map(impl_labels).fillna(df_latency["implementation"])
    )

    # pivot: rows = (system, implementation), columns = payload
    table_latency = (
        df_latency
        .pivot(
            index=["system_label", "implementation_label"],
            columns="total_size",
            values="cell"
        )
        .sort_index(axis=0, level=[0, 1])
        .sort_index(axis=1)
    )
    table_latency.index.names = [None, None]

    # rename payload column labels
    table_latency.columns = [format_payload(x) for x in table_latency.columns]
    table_latency.columns.name = None

    latex_str = table_latency.to_latex(
        escape=False,
        caption="Latency standard deviation in ms for different payload sizes.",
        label="tab:latency_std",
        multicolumn=True,
        multicolumn_format='c',
        multirow=True,
        na_rep="--",
    )

    with open(os.path.join(output_dir, "latency_table.tex"), "w") as f:
        f.write(latex_str)


def plot_heatmap(df_all):
    """Single-figure alternative to the line chart above: one row per
    system/implementation, one column per payload size, cell color = mean
    latency on a log-scaled single-hue sequential ramp, with the value
    annotated in each cell. Avoids the categorical-color ceiling the line
    chart hits (9 series) since identity is carried by row position, not hue.
    """
    df_lat = df_all[df_all["metric"] == "latency"].copy()
    if df_lat.empty:
        return

    pivot = df_lat.pivot(index="row_label", columns="total_size", values="mean").sort_index(axis=1)

    # Row order: fixed system order (matching the line chart's legend order),
    # Python before C/C++ within each system.
    row_order = []
    for sub in SUBFOLDERS:
        label = SYSTEM_LABELS.get(sub, sub)
        for impl in ["Python", "C"]:
            row_label = f"{label} ({impl})"
            if row_label in pivot.index:
                row_order.append(row_label)
    pivot = pivot.reindex(row_order)

    values = pivot.to_numpy(dtype=float)
    masked = np.ma.masked_invalid(values)

    # Validated single-hue sequential ramp (blue, 100->700 steps), per the
    # dataviz skill's reference palette for continuous/heatmap magnitude.
    seq_cmap = LinearSegmentedColormap.from_list(
        "seq_blue", ["#9ec5f4", "#5598e7", "#256abf", "#133d74", "#08264e"]
    )
    seq_cmap.set_bad("#e8e8e8")  # muted gray for missing data, not part of the scale

    # Cap vmax well below the true max: a couple of extreme outlier cells
    # (Dareplane's C tail latencies, into the millions of µs) would otherwise
    # stretch the log range so far that the ~8-300us region everyone else
    # lives in collapses into one nearly-identical pale shade. Clipped cells
    # still show their exact value via the text annotation; only the color
    # saturates at the cap (signaled by the colorbar's "extend" arrow).
    vmin = np.nanmin(values)
    vmax = np.nanpercentile(values, 90)
    norm = LogNorm(vmin=vmin, vmax=vmax)

    n_rows, n_cols = masked.shape
    fig, ax = plt.subplots(figsize=(0.55 * n_cols + 3, 0.4 * n_rows + 2))
    im = ax.imshow(masked, aspect="auto", cmap=seq_cmap, norm=norm)

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels([format_payload(x) for x in pivot.columns], rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(pivot.index, fontsize=9)

    ax.set_xlabel("Total Payload Size", fontsize=11, fontweight="bold")
    ax.set_title("Mean Latency by System and Payload Size", fontsize=12, fontweight="bold", pad=12)

    # Cell value annotations, with a text color that stays legible against
    # both the light and dark ends of the ramp.
    for i in range(n_rows):
        for j in range(n_cols):
            val = values[i, j]
            if np.isnan(val):
                ax.text(j, i, "n/a", ha="center", va="center", fontsize=7, color="#999999")
                continue
            frac = min(norm(val), 1.0)
            text_color = "white" if frac > 0.55 else "#1a1a1a"
            label = f"{val:.0f}" if val >= 10 else f"{val:.1f}"
            ax.text(j, i, label, ha="center", va="center", fontsize=7, color=text_color)

    # Thin white gaps between cells instead of a drawn border; no other chrome.
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    cbar = fig.colorbar(im, ax=ax, pad=0.02, extend="max")
    cbar.set_label("Latency (µs, log scale)", fontsize=10, fontweight="bold")

    fig.savefig(os.path.join(output_dir, "ipc_benchmark_heatmap.svg"), dpi=300, bbox_inches="tight")


def logspace_error_from_mean_std(mean, std):
    """Convert linear mean/std into asymmetric error bars suitable for a log axis."""
    mean = np.asarray(mean, dtype=float)
    std = np.asarray(std, dtype=float)

    yerr_lower = np.zeros_like(mean)
    yerr_upper = np.zeros_like(mean)

    valid = (mean > 0) & (std > 0)
    if np.any(valid):
        # Approximate the spread as log-normal so the interval remains positive
        # and visually symmetric on a logarithmic axis.
        log_sigma = np.sqrt(np.log1p((std[valid] / mean[valid]) ** 2))
        log_mu = np.log(mean[valid]) - 0.5 * log_sigma**2
        lower = np.exp(log_mu - log_sigma)
        upper = np.exp(log_mu + log_sigma)
        yerr_lower[valid] = np.maximum(mean[valid] - lower, 0)
        yerr_upper[valid] = np.maximum(upper - mean[valid], 0)

    return np.vstack([yerr_lower, yerr_upper])

# Load mean and std per file
for sub in SUBFOLDERS:
    # Check both results folders: Python and C implementations
    for results_folder, impl_type in [("rt_results", "Python"),("rt_c_results", "C")]:
    # for results_folder, impl_type in [("eike_rt_results", "Eike - Python"), ("eike_rt_c_results", "Eike - C"),("rt_results", "Linda - Python_RT"),("rt_c_results", "Linda - C_RT")]:

        results_dir = os.path.join(BASE_DIR, sub, results_folder)
        if not os.path.exists(results_dir):
            print(f"Skipping {results_dir} - not found")
            continue
        
        for file in os.listdir(results_dir):
            match = pattern.match(file)
            if not match:
                continue
            
            num_channels, msg_size, type_ = match.groups()
            num_channels = int(num_channels)
            msg_size = int(msg_size)
            total_size = num_channels * msg_size * 8  # Assuming float64 (8 bytes) per channel
            
            try:
                df = pd.read_csv(os.path.join(results_dir, file))
            except Exception as e:
                print(f"Error reading {file}: {e}")
                continue

            record_base = {
                "system": sub,
                "implementation": impl_type,
                "num_channels": num_channels,
                "msg_size": msg_size,
                "total_size": total_size}
            
            if type_ == "Producer":
                # Extract send period statistics
                if "Send_period" in df.columns:
                    
                    data_records.append(record_base | {
                        "metric": "send_period",
                        "mean": float(df.loc[df["Metric"] == "mean", "Send_period"].values[0]),
                        "std": float(df.loc[df["Metric"] == "std", "Send_period"].values[0]),
                        "max": float(df.loc[df["Metric"] == "max", "Send_period"].values[0]),
                    })
            
            else:  # Consumer (recv)
                # Extract latency and recv_period statistics
                if "Latency" in df.columns:
                    
                    data_records.append(record_base | {
                        "metric": "latency",
                        "mean": float(df.loc[df["Metric"] == "mean", "Latency"].values[0]),
                        "std": float(df.loc[df["Metric"] == "std", "Latency"].values[0]),
                        "max": float(df.loc[df["Metric"] == "max", "Latency"].values[0])
                    })
                    
                    data_records.append(record_base | {
                        "metric": "recv_period",
                        "mean": float(df.loc[df["Metric"] == "mean", "Recv_period"].values[0]),
                        "std": float(df.loc[df["Metric"] == "std", "Recv_period"].values[0]),
                        "max": float(df.loc[df["Metric"] == "max", "Recv_period"].values[0])
                    })
                    
                    data_records.append(record_base | {
                        "metric": "throughput",
                        "mean": float(df.loc[df["Metric"] == "mean", "Throughput"].values[0]) * total_size,
                        "std": 0,
                        "max": 0
                    })

df_all = pd.DataFrame(data_records)
df_all["system_label"] = df_all["system"].map(SYSTEM_LABELS).fillna(df_all["system"])
df_all["row_label"] = df_all["system_label"] + " (" + df_all["implementation"] + ")"

# aggregate duplicate entries
df_all = (df_all.groupby(
                    [
                        "system",
                        "system_label",
                        "implementation",
                        "row_label",
                        "metric",
                        "total_size",
                    ], as_index=False
                ).agg(
                    mean=("mean", "mean"),
                    std=("std", "mean"),
                    max=("max", "mean"),
                ))

create_latex(df_all)

if df_all.empty:
    print("No data loaded. Check results directories and file names.")
else:
    print(f"Loaded {len(df_all)} records")

    plot_heatmap(df_all)

    def plot_metric(ax, metric, ylabel):
        """Plot a single metric across all systems and implementations"""
        for system in sorted(df_all['system'].unique()):
            color = SYSTEM_COLORS.get(system, None)
            
            for impl in sorted(df_all['implementation'].unique()):
                df_sys = df_all[
                    (df_all['system'] == system) &
                    (df_all['implementation'] == impl) &
                    (df_all['metric'] == metric)
                ]
                
                if df_sys.empty:
                    continue
                
                df_plot = df_sys.sort_values("total_size")
                
                x = df_plot["total_size"].values
                y_mean = df_plot["mean"].values
                y_std = df_plot["std"].values
                y_max = df_plot["max"].values
                
                # Use different markers for different implementations
                if impl == "Python":
                    marker = "o"
                    linestyle = "-"
                elif impl == "C":
                    marker = "o"
                    linestyle = "--"

                # ax.plot(
                #     x, y_mean,
                #     color=color,
                #     marker=marker,
                #     linestyle=linestyle,
                #     linewidth=1.5,
                #     markersize=5,
                # )
                
                # Plot mean line with asymmetric error bars scaled for a log axis.
                ax.errorbar(
                    x,
                    y_mean,
                    yerr=logspace_error_from_mean_std(y_mean, y_std),
                    color=color,
                    marker=marker,
                    linestyle=linestyle,
                    label=f"{system} ({impl})",
                    linewidth=1.5,
                    markersize=6,
                    capsize=3,
                    capthick=1,
                    elinewidth=1,
                )
        
        ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.grid(True, which="major", alpha=0.7, linewidth=0.8)
        ax.grid(True, which="minor", alpha=0.5, linewidth=0.5)
    
    # Create figure with 4 subplots
    fig = plt.figure(figsize=(10,14))
    ax = plt.subplot(1, 1, 1)

    cross_x = 80000 * 8 # Corresponds to msg_size 2000 and num_channels 40
    
    # plot_metric(ax, "throughput", "Throughput (Bytes/ms)")
    # ax.axhline(y=10, color='black', linestyle='-', linewidth=1.5, alpha=0.7)

    plot_metric(ax, "latency", "Latency (µs)")
    ax.axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)

    # plot_metric(axes[1], "recv_period", "Receive Period (µs)")
    # axes[1].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)

    # plot_metric(axes[2], "send_period", "Send Period (µs)")
    # axes[2].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    
    ax.set_xlabel("Total Payload Size (Bytes)", fontsize=11, fontweight='bold')

    # Set x lim for all subplots
    ax.set_xlim(5, 8000 * 40 * 8)
    # axes[1].set_xlim(5, 8000 * 40 * 8)
    # axes[2].set_xlim(5, 8000 * 40 * 8)


    # Only include systems that are actually present in the data
    systems_present = [s for s in SUBFOLDERS if s in df_all["system"].unique()]

    # System legend: colors
    system_handles = [
        Line2D([0], [0], color=SYSTEM_COLORS[s], lw=2, marker='None',
               label=SYSTEM_LABELS.get(s, s))
        for s in systems_present
    ]

    # Implementation legend: marker/style semantics
    impl_handles = [
        Line2D([0], [0], color='black', lw=1.5, marker='',
               linestyle='-', markersize=5, label='Python'),
        Line2D([0], [0], color='black', lw=1.5, marker='',
               linestyle='--', markersize=5, label='C/C++'),
    ]

    legend1 = fig.legend(
        handles=system_handles,
        loc='upper left',
        bbox_to_anchor=(0.83, 0.65),
        ncol=1,
        title="System",
        frameon=False,
        fontsize=10,
        title_fontsize=10,
        borderaxespad=0.0,
        alignment='left'
    )

    legend2 = fig.legend(
        handles=impl_handles,
        loc='upper left',
        bbox_to_anchor=(0.83, 0.4),
        ncol=1,
        title="Implementation",
        frameon=False,
        fontsize=10,
        title_fontsize=10,
        borderaxespad=0.0,
        alignment='left'
    )
    # Leave a dedicated right margin for legends
    fig.subplots_adjust(left=0.10, right=0.80, top=0.95, bottom=0.08, hspace=0.08)
    
    plt.savefig(os.path.join(output_dir, "ipc_benchmark_comparison.svg"), dpi=300, bbox_inches="tight")
    plt.show()