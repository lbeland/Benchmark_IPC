## Setup
You need the following files in the parent folder: 
- benchmark_all.py
- plot_benchmark_throughput.py

and than the repos `zeromq_diy` and `falcon_core develop` as subfolders

install requirements for plotting:
```bash
 pip install -r requirements.txt
```

## Perform benchmarking:
```bash
sudo -E python3 benchmark_all.py 
```
sudo is needed so that subprocesses can run with specified priority of 99.
Use --overwrite if you run multiple times to override old results

## Plot Results:
```bash
python3 plot_benchmark_throughput.py
```
Right now all results are saved as 'rt_' results (real-time kernel), this is hardcoded, so if your system is not running with a RT-Kernel, just ignore it