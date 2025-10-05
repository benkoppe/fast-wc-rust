# rust-bench

The benchmark code for `fast-wc-rust` is designed to test many configurations,
as well as compare performance with competitor codes.

Output for this benchmark is stored here, in the `criterion` directory.
View `criterion/report/index.html` to see detailed results.
Run `do-compare.sh` to run the benchmark and copy results to this directory.

This folder also uses `uv` and a Python script to graph top performance between Rust and C++ code.
To run, generate the `criterion` results first, then download uv, and run:

```bash
uv run benchmark_comparison.py
```
