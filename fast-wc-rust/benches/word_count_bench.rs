use criterion::{BenchmarkId, Criterion, Throughput, criterion_group, criterion_main};
use fast_wc_rust::{Config, FastWordCounter};
use std::fs;
use std::hint::black_box;
use std::io::Write;
use std::process::Command;
use tempfile::TempDir;

const CPP_BINARY: &str = "../competitors/fast-cpp/fast-wc";

fn run_cpp_benchmark(temp_dir: &TempDir, num_threads: usize, parallel_merge: bool) -> bool {
    // let mut cmd = Command::new("taskset");
    // cmd.arg("0xFF")
    // .arg(CPP_BINARY)
    let mut binding = Command::new(CPP_BINARY);
    let cmd = binding
        .arg(format!("-n{}", num_threads))
        // .arg("-b2")
        .arg("-s");

    if parallel_merge {
        cmd.arg("-p");
    }

    cmd.arg(temp_dir.path());

    let status = cmd
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();

    match status {
        Ok(status) => status.success(),
        Err(e) => {
            eprintln!("Failed to run C++ binary: {e}");
            false
        }
    }
}

fn create_test_files(dir: &TempDir, num_files: usize, file_size: usize) -> Vec<String> {
    let words = [
        "int", "main", "void", "return", "printf", "char", "const", "struct", "typedef", "static",
        "extern", "inline", "register", "volatile", "sizeof", "malloc", "free", "memcpy", "strlen",
        "strcpy", "strcmp", "file", "buffer", "pointer", "array", "function", "variable", "hello",
        "world", "test", "example", "sample", "data", "string",
    ];

    let mut file_paths = Vec::new();

    for i in 0..num_files {
        let file_path = dir.path().join(format!("test_{}.c", i));
        let mut file = fs::File::create(&file_path).unwrap();

        let mut content = String::with_capacity(file_size);
        let mut size = 0;

        while size < file_size {
            for word in &words {
                content.push_str(word);
                content.push(' ');
                size += word.len() + 1;

                if size >= file_size {
                    break;
                }

                if size % 100 == 0 {
                    content.push('\n');
                    size += 1;
                }
                if size % 50 == 0 {
                    content.push_str("();");
                    size += 3;
                }
            }
        }

        file.write_all(content.as_bytes()).unwrap();
        file_paths.push(file_path.to_string_lossy().to_string());
    }

    file_paths
}

fn bench_word_counting(c: &mut Criterion) {
    let temp_dir = TempDir::new().unwrap();

    // Test different file sizes and counts
    let test_cases = [
        (10, 1024),   // 10 small files (1KB each)
        (100, 1024),  // 100 small files
        (10, 10240),  // 10 medium files (10KB each)
        (50, 10240),  // 50 medium files
        (10, 102400), // 10 large files (100KB each)
    ];

    let mut group = c.benchmark_group("word_counting");

    for (num_files, file_size) in test_cases {
        let total_size = num_files * file_size;
        group.throughput(Throughput::Bytes(total_size as u64));

        create_test_files(&temp_dir, num_files, file_size);

        let mut thread_counts = vec![1, 2, 4, 8];
        let num_cpus = num_cpus::get();

        if !thread_counts.contains(&num_cpus) {
            thread_counts.push(num_cpus);
            thread_counts.sort_unstable();
        }

        // Benchmark with different configurations
        for num_threads in thread_counts {
            if num_threads <= num_cpus {
                for parallel_merge in [true, false] {
                    let merge_suffix = if parallel_merge {
                        "parallel_merge"
                    } else {
                        "sequential_merge"
                    };

                    group.bench_with_input(
                        BenchmarkId::new(
                            format!("mmap_threads_{}_{}", num_threads, merge_suffix),
                            format!("{}files_{}bytes", num_files, file_size),
                        ),
                        &(num_files, file_size),
                        |b, _| {
                            let config = Config {
                                num_threads,
                                use_mmap: true,
                                silent: true,
                                parallel_merge,
                            };
                            let counter = FastWordCounter::new(config);

                            b.iter(|| black_box(counter.count_directory(temp_dir.path()).unwrap()));
                        },
                    );

                    group.bench_with_input(
                        BenchmarkId::new(
                            format!("read_threads_{}_{}", num_threads, merge_suffix),
                            format!("{}files_{}bytes", num_files, file_size),
                        ),
                        &(num_files, file_size),
                        |b, _| {
                            let config = Config {
                                num_threads,
                                use_mmap: false,
                                silent: true,
                                parallel_merge,
                            };
                            let counter = FastWordCounter::new(config);

                            b.iter(|| black_box(counter.count_directory(temp_dir.path()).unwrap()));
                        },
                    );

                    // Benchmark against C++ binary with matching configuration
                    if Command::new("taskset").arg("--version").output().is_ok()
                        && Command::new(CPP_BINARY).arg("--help").output().is_ok()
                    {
                        group.bench_with_input(
                            BenchmarkId::new(
                                format!("cpp_threads_{}_{}", num_threads, merge_suffix),
                                format!("{}files_{}bytes", num_files, file_size),
                            ),
                            &(num_files, file_size),
                            |b, _| {
                                b.iter(|| {
                                    black_box(run_cpp_benchmark(
                                        &temp_dir,
                                        num_threads,
                                        parallel_merge,
                                    ))
                                })
                            },
                        );
                    }
                }
            }
        }

        // Clean up for next iteration
        for entry in fs::read_dir(temp_dir.path()).unwrap() {
            let entry = entry.unwrap();
            if entry.file_type().unwrap().is_file() {
                fs::remove_file(entry.path()).unwrap();
            }
        }
    }

    group.finish();
}

fn bench_rust_vs_cpp(c: &mut Criterion) {
    let temp_dir = TempDir::new().unwrap();

    let _ = create_test_files(&temp_dir, 50, 10240); // 50 files, 10KB each
    let total_size = 50 * 10240;

    let mut group = c.benchmark_group("rust_vs_cpp");
    group.throughput(Throughput::Bytes(total_size as u64));

    // Benchmark Rust implementation (optimal config)
    group.bench_function("rust_optimal", |b| {
        let config = Config {
            num_threads: num_cpus::get(),
            use_mmap: true,
            silent: true,
            parallel_merge: true,
        };
        let counter = FastWordCounter::new(config);

        b.iter(|| black_box(counter.count_directory(temp_dir.path()).unwrap()));
    });

    // Benchmark C++ binary with optimal configuration (if available)
    if Command::new("taskset").arg("--version").output().is_ok()
        && Command::new(CPP_BINARY).arg("--help").output().is_ok()
    {
        group.bench_function("cpp_binary", |b| {
            b.iter(|| black_box(run_cpp_benchmark(&temp_dir, num_cpus::get(), true)));
        });
    }

    group.finish();
}

criterion_group!(benches, bench_word_counting, bench_rust_vs_cpp);
criterion_main!(benches);
