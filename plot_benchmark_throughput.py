import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import LogNorm, LinearSegmentedColormap
import re
import matplotlib as mpl

mpl.rcParams.update({
    "font.size": 7,
    "pgf.texsystem": "pdflatex",
    'font.family': 'serif',
    'text.usetex': True,
    'pgf.rcfonts': False,
})


PLOTS_DIR = "/home/linda/Documents/MA/plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

TEXTWIDTH    = 6.30045
ASPECT_RATIO = 6/19
SCALE        = 1.0
FIG_WIDTH    = TEXTWIDTH * SCALE
FIG_HEIGHT   = FIG_WIDTH * ASPECT_RATIO * 1.8
FIGSIZE      = (FIG_WIDTH, FIG_HEIGHT)


def save_pgf(fig, name: str) -> None:
    fig.savefig(os.path.join(PLOTS_DIR, f"{name}.pgf"), bbox_inches="tight")

def save_png(fig, name: str) -> None:
    fig.savefig(os.path.join(PLOTS_DIR, f"{name}.png"), bbox_inches="tight", dpi=300)

def save_pdf(fig, name: str) -> None:
    fig.savefig(os.path.join(PLOTS_DIR, f"{name}.pdf"), bbox_inches="tight")

SUBFOLDERS = ["dareplane", "bifrost", "brand-tutorial", "zeromq_diy", "multiprocessing_diy", "falcon-core-develop", ]
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
    "bifrost": "Bifrost",
    "dareplane": "Dareplane",
    "brand-tutorial": "BRAND",
    "zeromq_diy": "ZeroMQ",
    "falcon-core-develop": "Falcon",
    "multiprocessing_diy": "Multiprocessing"
}

def mad(data, axis=None):
    """Mean absolute deviation"""
    return np.mean(np.abs(data - np.mean(data, axis)), axis)

def format_payload(x):
    """Binary size label using base-1024 units: B / KiB / MiB.
    Sub-unit values keep up to two decimals (e.g. 1310720 -> "1.25 MiB")."""
    x = int(x)
    for factor, unit in ((1024 ** 2, "MiB"), (1024, "KiB")):
        if x >= factor:
            s = f"{x / factor:.2f}".rstrip("0").rstrip(".")
            return f"{s} {unit}"
    return f"{x} B"

def fmt_max3(val):
    """Format a cell value with at most three digits; k / M suffixes carry
    the magnitude so e.g. 12345 -> "12k" and 1.5e6 -> "1.5M"."""
    v = float(val)
    for div, suf in ((1.0, ""), (1e3, "k"), (1e6, "M")):
        s = v / div
        if abs(s) < 999.5:
            return f"{s:.1f}{suf}" if abs(s) < 9.95 else f"{s:.0f}{suf}"
    return f"{v/1e6:.0f}M"

TARGET_PAYLOADS = [8, 1024, 16 * 1024, 1280 * 1024]  # 8 B, 1 KiB, 16 KiB, 1.25 MiB

# (system, implementation) pairs kept in the jitter table
JITTER_SYSTEMS = [
    ("zeromq_diy", "C"),
    ("multiprocessing_diy", "Python"),
    ("falcon-core-develop", "C++"),
]

def create_latex(df_all):
    """Write the latency-jitter table as a hand-built booktabs LaTeX table:
    one row per (system, implementation) in JITTER_SYSTEMS, one column per
    payload in TARGET_PAYLOADS. Cell = mean-absolute latency jitter in us."""
    df_latency = df_all[
        (df_all["metric"] == "latency")
        & (df_all["total_size"].isin(TARGET_PAYLOADS))
    ]

    impl_labels = {"Python": "Python", "C": "C/C++"}

    # (system, implementation) -> {total_size: jitter_us}
    jitter = {}
    for _, r in df_latency.iterrows():
        jitter.setdefault((r["system"], r["implementation"]), {})[r["total_size"]] = r["std"]

    payloads = sorted(TARGET_PAYLOADS)
    header_cols = ["System"] + [format_payload(p) for p in payloads]
    col_spec = "l" + "c" * len(payloads)

    lines = [
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption[Latency jitter in $\mu$s for different payload sizes]{}",
        r"\label{tab:latency_jitter}",
        rf"\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        " & ".join(header_cols) + r" \\",
        r"\midrule",
    ]

    for system, impl in JITTER_SYSTEMS:
        label = SYSTEM_LABELS.get(system, system)
        row_label = f"{label} ({impl_labels.get(impl, impl)})"
        row_vals = jitter.get((system, impl), {})
        cells = [row_label]
        for p in payloads:
            v = row_vals.get(p)
            cells.append(f"{v:.3f}" if v is not None and pd.notna(v) else "--")
        lines.append(" & ".join(cells) + r" \\")

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]

    with open(os.path.join(PLOTS_DIR, "latency_table.tex"), "w") as f:
        f.write("\n".join(lines) + "\n")


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
    # Python before C/C++ within each system. Display label differs from the
    # underlying data label: Python -> "py", and C -> "C++" for Falcon (the
    # only C++ implementation here), "C" for everyone else.
    row_order = []
    display_labels = {}
    for sub in SUBFOLDERS:
        label = SYSTEM_LABELS.get(sub, sub)
        for impl in ["Python", "C"]:
            row_label = f"{label} ({impl})"
            if row_label in pivot.index:
                row_order.append(row_label)
                if impl == "Python":
                    impl_display = "Py"
                else:
                    impl_display = "C++" if sub == "falcon-core-develop" else "C"
                display_labels[row_label] = f"{label} ({impl_display})"
    pivot = pivot.reindex(row_order)
    row_display_labels = [display_labels[r] for r in pivot.index]

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
    # fig, ax = plt.subplots(figsize=(0.55 * n_cols + 3, 0.4 * n_rows + 2))
    fig, ax = plt.subplots(figsize=FIGSIZE)
    im = ax.imshow(masked, aspect="auto", cmap=seq_cmap, norm=norm)

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels([format_payload(x) for x in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(row_display_labels)#, rotation=30, ha="left")

    ax.set_xlabel("Payload size")

    # Cell value annotations, with a text color that stays legible against
    # both the light and dark ends of the ramp.
    for i in range(n_rows):
        for j in range(n_cols):
            val = values[i, j]
            if np.isnan(val):
                ax.text(j, i, "n/a", ha="center", va="center", fontsize=5, color="#999999")
                continue
            frac = min(norm(val), 1.0)
            text_color = "white" if frac > 0.55 else "#1a1a1a"
            label = fmt_max3(val)
            ax.text(j, i, label, ha="center", va="center", fontsize=5, color=text_color)

    # Thin white gaps between cells instead of a drawn border; no other chrome.
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1)
    ax.tick_params(which="major", length=0,pad=0.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.set_yticklabels(row_display_labels, ha="right")
    for spine in ax.spines.values():
        spine.set_visible(False)

    cbar = fig.colorbar(im, ax=ax, orientation="horizontal", location="top", pad=0.1, fraction=0.05, aspect=40, extend="max")
    cbar.set_label("Latency [µs]")

    fig.tight_layout()

    save_pgf(fig, "ipc_benchmark_heatmap")
    save_pdf(fig, "ipc_benchmark_heatmap")
    # save_png(fig, "ipc_benchmark_heatmap")


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

        results_dir = os.path.join("./", sub, results_folder)
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
                    mean_val = float(df.loc[df["Metric"] == "mean", "Latency"].values[0])
                    max_val = float(df.loc[df["Metric"] == "max", "Latency"].values[0])

                    # Try to compute jitter from per-packet process_times file
                    base = file[:-4] if file.lower().endswith('.csv') else file
                    proc_path = os.path.join(results_dir, base + "_process_times.csv")
                    jitter = None
                    try:
                        if os.path.exists(proc_path):
                            samples = np.loadtxt(proc_path, dtype=float)
                            if samples.size > 1:
                                # samples are in seconds; convert to microseconds
                                lat_us = samples * 1e6
                                jitter = float(np.mean(np.abs(np.diff(lat_us))))
                    except Exception:
                        jitter = None

                    if jitter is None:
                        try:
                            jitter = float(df.loc[df["Metric"] == "std", "Latency"].values[0])
                        except Exception:
                            jitter = 0.0

                    data_records.append(record_base | {
                        "metric": "latency",
                        "mean": mean_val,
                        "std": jitter,
                        "max": max_val
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

    # def plot_metric(ax, metric, ylabel):
    #     """Plot a single metric across all systems and implementations"""
    #     for system in sorted(df_all['system'].unique()):
    #         color = SYSTEM_COLORS.get(system, None)
            
    #         for impl in sorted(df_all['implementation'].unique()):
    #             df_sys = df_all[
    #                 (df_all['system'] == system) &
    #                 (df_all['implementation'] == impl) &
    #                 (df_all['metric'] == metric)
    #             ]
                
    #             if df_sys.empty:
    #                 continue
                
    #             df_plot = df_sys.sort_values("total_size")
                
    #             x = df_plot["total_size"].values
    #             y_mean = df_plot["mean"].values
    #             y_std = df_plot["std"].values
    #             y_max = df_plot["max"].values
                
    #             # Use different markers for different implementations
    #             if impl == "Python":
    #                 marker = "o"
    #                 linestyle = "-"
    #             elif impl == "C":
    #                 marker = "o"
    #                 linestyle = "--"
                
    #             # Plot mean line with asymmetric error bars scaled for a log axis.
    #             ax.errorbar(
    #                 x,
    #                 y_mean,
    #                 yerr=logspace_error_from_mean_std(y_mean, y_std),
    #                 color=color,
    #                 marker=marker,
    #                 linestyle=linestyle,
    #                 label=f"{system} ({impl})",
    #                 linewidth=1.5,
    #                 markersize=6,
    #                 capsize=3,
    #                 capthick=1,
    #                 elinewidth=1,
    #             )
        
    #     ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
    #     ax.set_xscale("log")
    #     ax.set_yscale("log")
    #     ax.grid(True, which="major", alpha=0.7, linewidth=0.8)
    #     ax.grid(True, which="minor", alpha=0.5, linewidth=0.5)
    
    # # Create figure with 4 subplots
    # fig = plt.figure(figsize=(10,14))
    # ax = plt.subplot(1, 1, 1)

    # cross_x = 80000 * 8 # Corresponds to msg_size 2000 and num_channels 40
    
    # # plot_metric(ax, "throughput", "Throughput (Bytes/ms)")
    # # ax.axhline(y=10, color='black', linestyle='-', linewidth=1.5, alpha=0.7)

    # plot_metric(ax, "latency", "Latency (µs)")
    # ax.axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)

    # # plot_metric(axes[1], "recv_period", "Receive Period (µs)")
    # # axes[1].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)

    # # plot_metric(axes[2], "send_period", "Send Period (µs)")
    # # axes[2].axhline(y=100, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    
    # ax.set_xlabel("Total Payload Size (Bytes)", fontsize=11, fontweight='bold')

    # # Set x lim for all subplots
    # ax.set_xlim(5, 8000 * 40 * 8)
    # # axes[1].set_xlim(5, 8000 * 40 * 8)
    # # axes[2].set_xlim(5, 8000 * 40 * 8)


    # # Only include systems that are actually present in the data
    # systems_present = [s for s in SUBFOLDERS if s in df_all["system"].unique()]

    # # System legend: colors
    # system_handles = [
    #     Line2D([0], [0], color=SYSTEM_COLORS[s], lw=2, marker='None',
    #            label=SYSTEM_LABELS.get(s, s))
    #     for s in systems_present
    # ]

    # # Implementation legend: marker/style semantics
    # impl_handles = [
    #     Line2D([0], [0], color='black', lw=1.5, marker='',
    #            linestyle='-', markersize=5, label='Python'),
    #     Line2D([0], [0], color='black', lw=1.5, marker='',
    #            linestyle='--', markersize=5, label='C/C++'),
    # ]

    # legend1 = fig.legend(
    #     handles=system_handles,
    #     loc='upper left',
    #     bbox_to_anchor=(0.83, 0.65),
    #     ncol=1,
    #     title="System",
    #     frameon=False,
    #     fontsize=10,
    #     title_fontsize=10,
    #     borderaxespad=0.0,
    #     alignment='left'
    # )

    # legend2 = fig.legend(
    #     handles=impl_handles,
    #     loc='upper left',
    #     bbox_to_anchor=(0.83, 0.4),
    #     ncol=1,
    #     title="Implementation",
    #     frameon=False,
    #     fontsize=10,
    #     title_fontsize=10,
    #     borderaxespad=0.0,
    #     alignment='left'
    # )
    # # Leave a dedicated right margin for legends
    # fig.subplots_adjust(left=0.10, right=0.80, top=0.95, bottom=0.08, hspace=0.08)
    
    # plt.savefig(os.path.join(output_dir, "ipc_benchmark_comparison.svg"), dpi=300, bbox_inches="tight")
    # plt.show()