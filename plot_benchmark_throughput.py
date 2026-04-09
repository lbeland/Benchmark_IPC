import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import re

BASE_DIR = "./"
SUBFOLDERS = ["bifrost", "zeromq_diy", "brand-tutorial", "dareplane", "falcon-core-develop"]
# SUBFOLDERS = ["zeromq_diy", "falcon-core-develop"]

data_records = []

# Updated pattern to match: num_channels_msg_size_[Consumer|Producer].csv
pattern = re.compile(r"(\d+)_(\d+)_(Consumer|Producer).csv")

SYSTEM_COLORS = {
    "bifrost": "tab:red",
    "dareplane": "tab:blue",
    "brand-tutorial": "tab:orange",
    "zeromq_diy": "tab:green",
    "falcon-core-develop": "tab:purple"
}

SYSTEM_LABELS = {
    "bifrost": "Bifrost",
    "dareplane": "Dareplane",
    "brand-tutorial": "BRAND",
    "zeromq_diy": "ZeroMQ",
    "falcon-core-develop": "Falcon",
}

def mad(data, axis=None):
    """Mean absolute deviation"""
    return np.mean(np.abs(data - np.mean(data, axis)), axis)


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
                        "max": float(df.loc[df["Metric"] == "max", "Send_period"].values[0])
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
                        "mean": float(df.loc[df["Metric"] == "mean", "Throughput"].values[0]),
                        "std": 0,
                        "max": 0
                    })

df_all = pd.DataFrame(data_records)

if df_all.empty:
    print("No data loaded. Check results directories and file names.")
else:
    print(f"Loaded {len(df_all)} records")
    
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

                # if there are multiple records for one size, take mean and std across them
                # df_plot = df_plot.groupby("total_size").agg({
                #     "mean": "mean",
                #     "std": "mean",
                #     "max": "mean"
                # }).reset_index()
                
                x = df_plot["total_size"].values
                y_mean = df_plot["mean"].values
                y_std = df_plot["std"].values
                y_max = df_plot["max"].values
                
                # Use different markers for different implementations
                if impl == "Python":
                    marker = "o"
                    linestyle = "-"
                elif impl == "C":
                    marker = "s"
                    linestyle = "--"

                ax.plot(
                    x, y_mean,
                    color=color,
                    marker=marker,
                    linestyle=linestyle,
                    linewidth=1.5,
                    markersize=5,
                )
                
                # # Plot mean line with asymmetric error bars scaled for a log axis.
                # ax.errorbar(
                #     x,
                #     y_mean,
                #     yerr=logspace_error_from_mean_std(y_mean, y_std),
                #     color=color,
                #     marker=marker,
                #     linestyle=linestyle,
                #     label=f"{system} ({impl})",
                #     linewidth=1,
                #     markersize=6,
                #     capsize=3,
                #     capthick=1,
                #     elinewidth=1,
                # )
        
        ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.grid(True, which="both", alpha=0.3)
    
    # Create figure with 4 subplots
    fig, axes = plt.subplots(3, 1, figsize=(12, 14), sharex=True)

    cross_x = 80000 * 8 # Corresponds to msg_size 2000 and num_channels 40
    
    # plot_metric(axes[0], "throughput", "Throughput (msg/ms)")
    # axes[0].axhline(y=10, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    # axes[0].axvline(x=cross_x, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    plot_metric(axes[0], "latency", "Latency (µs)")
    axes[0].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    # axes[0].axvline(x=cross_x, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    plot_metric(axes[1], "recv_period", "Receive Period (µs)")
    axes[1].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    # axes[1].axvline(x=cross_x, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    plot_metric(axes[2], "send_period", "Send Period (µs)")
    axes[2].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    # axes[2].axvline(x=cross_x, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    
    axes[2].set_xlabel("Total Payload Size (Bytes)", fontsize=11, fontweight='bold')

    # Set x lim for all subplots
    axes[0].set_xlim(5, 8000 * 40 * 8)
    axes[1].set_xlim(5, 8000 * 40 * 8)
    axes[2].set_xlim(5, 8000 * 40 * 8)


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
        Line2D([0], [0], color='black', lw=1.5, marker='o',
               linestyle='-', markersize=5, label='Python'),
        Line2D([0], [0], color='black', lw=1.5, marker='s',
               linestyle='--', markersize=5, label='C/C++'),
    ]

    legend1 = fig.legend(
        handles=system_handles,
        loc='upper left',
        bbox_to_anchor=(0.83, 0.82),
        ncol=1,
        title="System",
        frameon=True,
        fontsize=9,
        title_fontsize=10,
        borderaxespad=0.0,
    )

    legend2 = fig.legend(
        handles=impl_handles,
        loc='upper left',
        bbox_to_anchor=(0.83, 0.36),
        ncol=1,
        title="Implementation",
        frameon=True,
        fontsize=9,
        title_fontsize=10,
        borderaxespad=0.0,
    )

    fig.add_artist(legend1)

    fig.suptitle("IPC Benchmark Results Comparison (Python vs C/C++)",
                 fontsize=14, fontweight='bold', y=0.995)

    # Leave a dedicated right margin for legends
    fig.subplots_adjust(left=0.10, right=0.80, top=0.95, bottom=0.08, hspace=0.08)
    
    plt.savefig("ipc_benchmark_comparison.svg", dpi=300)
    plt.show()