use anyhow::Result;
use clap::Parser;
use fast_wc_rust::{Config, FastWordCounter};
use std::path::PathBuf;
use std::time::Instant;

#[derive(Parser)]
#[command(name = "fast-wc-rust")]
#[command(about = "High-performance word counter for C/H files")]
#[command(version)]
struct Args {
    /// Directory to scan for .c and .h files
    directory: PathBuf,

    /// Number of threads to use
    #[arg(short = 'n', long, default_value_t = num_cpus::get())]
    threads: usize,

    /// Use memory mapping for file I/O
    #[arg(short = 'm', long, default_value_t = true)]
    mmap: bool,

    /// Enable parallel merging
    #[arg(short = 'p', long)]
    parallel_merge: bool,

    /// Silent mode (no progress output)
    #[arg(short = 's', long)]
    silent: bool,

    /// Show only top N results
    #[arg(short = 't', long)]
    top: Option<usize>,
}

fn main() -> Result<()> {
    let args = Args::parse();

    let config = Config {
        num_threads: args.threads,
        use_mmap: args.mmap,
        silent: args.silent,
        parallel_merge: args.parallel_merge,
    };

    if !args.silent {
        println!(
            "fast-wc-rust with {} threads, nmap: {}, parallel merge: {}",
            args.threads, args.mmap, args.parallel_merge
        )
    }

    let counter = FastWordCounter::new(config);
    let start = Instant::now();

    let results = counter.count_directory(&args.directory)?;

    let elapsed = start.elapsed();

    if !args.silent {
        println!("Processing completed in {:.2?}", elapsed);
        println!("Found {} unique words", results.len());
        println!();
    }

    let display_results = if let Some(top) = args.top {
        &results[..results.len().min(top)]
    } else {
        &results
    };

    counter.print_results(display_results);

    Ok(())
}
