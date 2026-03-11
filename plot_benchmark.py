import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

BASE_DIR = "./"
SUBFOLDERS = ["bifrost", "zeromq_diy", "brand-tutorial", "dareplane"]
data_records = []

pattern = re.compile(r"(\d+)_(\d+)_(\d+)_(send|recv)_times\.csv")

SYSTEM_COLORS = {
    "bifrost": "tab:red",
    "dareplane": "tab:blue",
    "brand-tutorial": "tab:orange",
    "zeromq_diy": "tab:green",
}

FREQS = [1000,2000,5000,10000]

def mad(data, axis=None):
    return np.mean(np.abs(data - np.mean(data, axis)), axis)

# Load mean and std per file
for sub in SUBFOLDERS:
    results_dir = os.path.join(BASE_DIR, sub, "results_2")
    if not os.path.exists(results_dir):
        continue
    for file in os.listdir(results_dir):
        match = pattern.match(file)
        if not match:
            continue
        
        freq, msg_size, num_channels, type_ = match.groups()
        freq = int(freq)
        msg_size = int(msg_size)
        num_channels = int(num_channels)
        total_size = num_channels * msg_size
        
        try:
            df = pd.read_csv(os.path.join(results_dir, file))
        except:
            continue
        
        if type_ == "send":
            mean_val = df['send_period'][:-1].mean() * 1e3
            std_val = mad(df['send_period'][:-1]) * 1e3
            data_records.append({
                "system": sub,
                "freq": freq,
                "msg_size": msg_size,
                "num_channels": num_channels,
                "total_size": total_size,
                "metric": "send_jitter",
                "mean": mean_val,
                "std": std_val
            })
        else:  # recv
            mean_latency = df['latency'].mean() * 1e3
            std_latency = df['latency'].std() * 1e3

            mean_recv_jitter = df['recv_period'][:-1].mean() * 1e3
            std_recv_jitter = df['recv_period'][:-1].std() * 1e3

            data_records.append({
                "system": sub,
                "freq": freq,
                "msg_size": msg_size,
                "num_channels": num_channels,
                "total_size": total_size,
                "metric": "avg_latency",
                "mean": mean_latency,
                "std": std_latency
            })

            data_records.append({
                "system": sub,
                "freq": freq,
                "msg_size": msg_size,
                "num_channels": num_channels,
                "total_size": total_size,
                "metric": "recv_jitter",
                "mean": mean_recv_jitter,
                "std": std_recv_jitter
            })

df_all = pd.DataFrame(data_records)

def plot_metric(fig, ax, metric, ylabel, freq):

    for system in sorted(df_all['system'].unique()):
        color = SYSTEM_COLORS.get(system, None)
        df_sys = df_all[
            (df_all['system'] == system) &
            (df_all['metric'] == metric)
        ]

        df_plot = df_sys[df_sys['freq'] == freq].sort_values("total_size")

        x = df_plot["total_size"]
        y = df_plot["mean"]
        yerr = df_plot["std"]

        # Mean line
        ax.plot(
            x, y,
            # linestyle=linestyle,
            color=color,
            marker="o",
            label=f"{system}"
        )

        # Std band
        ax.fill_between(
            x,
            y - yerr,
            y + yerr,
            color=color,
            alpha=0.1
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylabel(ylabel)
    

# Plot
for freq in FREQS:
    fig,ax = plt.subplots(3,1, figsize=(10, 18), sharex=True)
    plot_metric(fig, ax[0], "avg_latency", "Average Latency (ms)", freq)
    plot_metric(fig, ax[1], "send_jitter", "Send Jitter (ms)", freq)
    ax[2].sharey(ax[1])
    plot_metric(fig, ax[2], "recv_jitter", "Receive Jitter (ms)", freq)
    ax[2].set_xlabel("Total Payload Size (num_channels × msg_size)")
    handles, labels = ax[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.95), ncol=5)
    fig.suptitle(f"Benchmark Results at {freq} Hz")
plt.show()