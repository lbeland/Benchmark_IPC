now = time.monotonic()
send_ts = message.flat[0]

if pNumTicks[0] >= 0:
    recv_times.append(now)
    latencies.append(now - send_ts)

if pNumTicks[0] == n_messages - 1:
    recv_diffs = np.diff(recv_times)
    mean_recv = float(np.mean(recv_diffs)) * 1e6
    std_recv = float(np.std(recv_diffs)) * 1e6
    max_recv = float(np.max(recv_diffs)) * 1e6

    mean_lat = float(np.mean(latencies)) * 1e6
    std_lat = float(np.std(latencies)) * 1e6
    max_lat = float(np.max(latencies)) * 1e6

    duration_ms = (recv_times[-1] - recv_times[0]) * 1e3
    throughput = len(recv_times) / duration_ms if duration_ms > 0 else 0.0

    with open(output_file + "_Consumer.csv", "w") as f:
        f.write("Metric,Recv_period,Latency,Throughput\n")
        f.write(f"mean,{mean_recv},{mean_lat},{throughput}\n")
        f.write(f"std,{std_recv},{std_lat},\n")
        f.write(f"max,{max_recv},{max_lat},\n")
