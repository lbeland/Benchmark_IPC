now = time.monotonic()
message[...] = now

if pNumTicks[0] >= 0:
    send_times.append(now)

if pNumTicks[0] == n_messages - 1:
    print(f"Producer finished sending {n_messages} messages. Saving to {output_file}_Producer.csv")
    diffs = np.diff(send_times)
    mean_period = float(np.mean(diffs)) * 1e6
    std_period = float(np.std(diffs)) * 1e6
    max_period = float(np.max(diffs)) * 1e6

    with open(output_file + "_Producer.csv", "w") as f:
        f.write("Metric,Send_period\n")
        f.write(f"mean,{mean_period}\n")
        f.write(f"std,{std_period}\n")
        f.write(f"max,{max_period}\n")
