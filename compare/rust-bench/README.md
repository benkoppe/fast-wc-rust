# rust-bench

The benchmark code for `fast-wc-rust` is designed to test many configurations,
as well as compare performance with competitor codes.

Output for this benchmark is stored here, in the `criterion` directory.
View `criterion/report/index.html` to see detailed results.
Run `do-compare.sh` to run the benchmark and copy results to this directory.

NOTE: This comparison is now only a benchmark of different configurations of the Rust code.
The python graphing code has been removed.
It was an unfair comparison anyway, and I couldn't get the c++ call to stop breaking at >= 4 threads.
