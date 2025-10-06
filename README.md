# fast-wc-rust

A high-performance word counting tool for C and header files, implemented in Rust with multiple optimization strategies. Relies on multiple dependencies.

## Table of Contents

- [Comparison Results](#comparison-results)
- [Overview](#overview)
- [Features](#features)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Usage](#usage)
- [Benchmarking](#benchmarking)
- [Performance Comparison](#performance-comparison)
- [Project Structure](#project-structure)
- [Algorithm](#algorithm)
- [Testing](#testing)

## Comparison Results

I wasn't sure where I could find the original benchmark used for the slide. These bechmarks are instead composed with a python script that generates many large dummy ".c" and ".h" files, found in `compare/generate-files/`.

Here are some (trimmed) results of the `hyperfine` benchmarking output:

With 80 files, 4,738,771 total lines, total size 171.63 MB (0.168 GB):
```bash
Benchmarking with hyperfine...
Summary
  fast-wc-rust --threads 8 -p --silent ./generated_input/ ran
    1.01 ± 0.04 times faster than fast-wc-rust --threads 8 --silent ./generated_input/
    2.01 ± 0.08 times faster than fast-wc -n8 -b4 -s ./generated_input/
    2.09 ± 0.07 times faster than fast-wc -n8 -b2 -p -s ./generated_input/
    2.13 ± 0.16 times faster than fast-wc -n8 -b8 -s ./generated_input/
    2.14 ± 0.14 times faster than fast-wc -n8 -b4 -p -s ./generated_input/
    2.15 ± 0.14 times faster than fast-wc -n8 -b2 -s ./generated_input/
    2.15 ± 0.17 times faster than fast-wc -n8 -b8 -p -s ./generated_input/
    2.20 ± 0.09 times faster than fast-wc -n8 -b1 -s ./generated_input/
    2.31 ± 0.17 times faster than fast-wc -n8 -b1 -p -s ./generated_input/
```

With 1 file, 94,778 total lines, total size 3.37 MB (0.003 GB):
```bash
Benchmarking with hyperfine...
Summary
  fast-wc-rust --threads 8  --silent ./generated_input/ ran
    1.12 ± 0.35 times faster than fast-wc-rust --threads 8 -p --silent ./generated_input/
    1.78 ± 0.52 times faster than fast-wc -n8  -s ./generated_input/
    1.84 ± 0.54 times faster than fast-wc -n8 -p -s ./generated_input/
```

With 320 files, 19,551,563 total lines, total size 708.37 MB (0.692 GB):
```bash
Benchmarking with hyperfine...
Summary
  fast-wc-rust --threads 8 -p --silent ./generated_input/ ran
    1.00 ± 0.05 times faster than fast-wc-rust --threads 8 --silent ./generated_input/
    2.04 ± 0.12 times faster than fast-wc -n8 -b8 -s ./generated_input/
    2.04 ± 0.11 times faster than fast-wc -n8 -b8 -p -s ./generated_input/
    2.06 ± 0.09 times faster than fast-wc -n8 -b4 -p -s ./generated_input/
    2.10 ± 0.14 times faster than fast-wc -n8 -b4 -s ./generated_input/
    2.11 ± 0.10 times faster than fast-wc -n8 -b2 -p -s ./generated_input/
    2.12 ± 0.11 times faster than fast-wc -n8 -b2 -s ./generated_input/
    2.23 ± 0.13 times faster than fast-wc -n8 -b1 -s ./generated_input/
    2.23 ± 0.12 times faster than fast-wc -n8 -b1 -p -s ./generated_input/
```

These tests were completed on an 8-core, 32GB RAM (1GB SWAP) server container with an Intel(R) Xeon(R) W-2135 CPU @ 3.70GHz.

`taskset` wasn't used in these tests, because it only appeared to provide similar slowdown to both the Rust and C++ implementations with no benefit.

## Benchmark Results

The benchmark code has been modified to now only test different Rust configurations. Results of the `criterion.rs` report are hosted with a GitHub action here:

https://benkoppe.github.io/fast-wc-rust/report/

## Overview

`fast-wc-rust` is designed to efficiently count words (tokens) in C source files (.c) and header files (.h). It relies on multiple dependencies and implements several performance optimizations including:

- **Multi-threading**: Configurable number of worker threads
- **Memory mapping**: Optional memory-mapped file I/O for better performance
- **Parallel merging**: Parallel reduction of per-thread word counts
- **Fast tokenization**: Optimized character classification using lookup tables
- **Hash map optimization**: Uses `ahash` for faster hashing

## Features

- Scans directories recursively for `.c` and `.h` files
- Configurable threading (defaults to number of CPU cores)
- Memory-mapped I/O option for large files
- Parallel vs sequential result merging
- Performance statistics and benchmarking
- Silent mode for batch processing
- Top-N results filtering

## Dependencies

- `ahash` - Fast hashing algorithm
- `anyhow` - Error handling
- `clap` - Command line argument parsing
- `crossbeam` - Lock-free data structures and threading
- `memmap2` - Memory-mapped file I/O
- `num_cpus` - CPU core detection
- `rayon` - Data parallelism
- `walkdir` - Directory traversal

## Installation

```bash
cd fast-wc-rust
cargo build --release
```

## Usage

```bash
# Count words in current directory with default settings
./target/release/fast-wc-rust .

# Use specific number of threads
./target/release/fast-wc-rust -n 8 /path/to/source

# Disable memory mapping
./target/release/fast-wc-rust -m false /path/to/source

# Enable parallel merging and show only top 100 results
./target/release/fast-wc-rust -p -t 100 /path/to/source

# Silent mode (no progress output)
./target/release/fast-wc-rust -s /path/to/source
```

## Benchmarking

The project includes comprehensive benchmarks comparing different configurations. See `compare/rust-bench` for more.

## Performance Comparison

This implementation is benchmarked against a C++ reference implementation (`competitors/fast-cpp/`). The `compare/` directory contains:

- Tools for performance analysis, see `run-all.sh`
- Scripts to easily run benchmarking and python-assisted runtime comparison on large generated files.

See `compare/` for more.

## Project Structure

- `fast-wc-rust/` - Main Rust implementation
- `compare/` - Performance comparison tools and results
- `competitors/fast-cpp/` - C++ reference implementation
- Benchmark results are stored in `compare/rust-bench/criterion/`

## Algorithm

The word counting algorithm:

1. Discovers all `.c` and `.h` files recursively
2. Distributes files across worker threads
3. Each thread processes files using either memory mapping or standard I/O
4. Extracts words using optimized tokenization (alphanumeric + underscore)
5. Merges per-thread hash maps either sequentially or in parallel
6. Sorts results by count (descending) then alphabetically

## Testing

```bash
cd fast-wc-rust
cargo test
```
