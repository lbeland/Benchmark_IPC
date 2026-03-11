import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

BASE_DIR = "./"
SUBFOLDERS = ["bifrost", "zeromq_diy", "brand-tutorial", "dareplane", "falcon-core-develop"]
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

def mad(data, axis=None):
    """Mean absolute deviation"""
    return np.mean(np.abs(data - np.mean(data, axis)), axis)

# Load mean and std per file
for sub in SUBFOLDERS:
    # Check both results folders: Python and C implementations
    for results_folder, impl_type in [("results", "Python"), ("c_results", "C"),("rt_results", "Python_RT"),("rt_c_results", "C_RT")]:
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
            total_size = num_channels * msg_size
            
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
                    linestyle = "-"
                elif impl == "Python_RT":
                    marker = "o"
                    linestyle = ":"
                elif impl == "C_RT":
                    marker = "s"
                    linestyle = ":"
                
                # Plot mean line
                ax.plot(
                    x, y_mean,
                    color=color,
                    marker=marker,
                    linestyle=linestyle,
                    label=f"{system} ({impl})",
                    linewidth=2,
                    markersize=6
                )
                
                # Plot error band (std)
                ax.fill_between(
                    x,
                    y_mean - y_std,
                    y_mean + y_std,
                    color=color,
                    alpha=0.15
                )
        
        ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.grid(True, which="both", alpha=0.3)
    
    # Create figure with 4 subplots
    fig, axes = plt.subplots(4, 1, figsize=(12, 14), sharex=True)
    
    plot_metric(axes[0], "throughput", "Throughput (msg/ms)")
    axes[0].axhline(y=10, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    axes[0].axvline(x=80000, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    plot_metric(axes[1], "latency", "Latency (µs)")
    axes[1].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    axes[1].axvline(x=80000, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    plot_metric(axes[2], "recv_period", "Receive Period (µs)")
    axes[2].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    axes[2].axvline(x=80000, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    plot_metric(axes[3], "send_period", "Send Period (µs)")
    axes[3].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    axes[3].axvline(x=80000, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    
    axes[3].set_xlabel("Total Payload Size (num_channels × msg_size)", fontsize=11, fontweight='bold')
    
    # Create combined legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.99), 
               ncol=4, fontsize=8, frameon=True)
    
    fig.suptitle("IPC Benchmark Results Comparison (Python vs C)", fontsize=14, fontweight='bold', y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    
    plt.show()