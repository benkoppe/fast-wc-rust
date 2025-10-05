use ahash::AHashMap;
use anyhow::{Context, Result};
use crossbeam::channel::bounded;
use memmap2::Mmap;
use rayon::prelude::*;
use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use walkdir::WalkDir;

const TOKEN_CHARS: [bool; 256] = {
    let mut chars = [false; 256];
    let valid = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_";
    let mut i = 0;
    while i < valid.len() {
        chars[valid[i] as usize] = true;
        i += 1;
    }
    chars
};

#[inline(always)]
pub fn is_token_char(c: u8) -> bool {
    TOKEN_CHARS[c as usize]
}

// Configuration for the word counter
#[derive(Debug, Clone)]
pub struct Config {
    pub num_threads: usize,
    pub use_mmap: bool,
    pub silent: bool,
    pub parallel_merge: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            num_threads: num_cpus::get(),
            use_mmap: true,
            silent: false,
            parallel_merge: true,
        }
    }
}

// Word counter
pub struct FastWordCounter {
    config: Config,
    stats: Arc<Stats>,
}

#[derive(Debug, Default)]
pub struct Stats {
    files_processed: AtomicU64,
    bytes_processed: AtomicU64,
}

impl FastWordCounter {
    pub fn new(config: Config) -> Self {
        Self {
            config,
            stats: Arc::new(Stats::default()),
        }
    }

    // Count words in all .c and .h files in a directory
    pub fn count_directory(&self, dir: &Path) -> Result<Vec<(String, u64)>> {
        let files = self.discover_files(dir)?;

        if !self.config.silent {
            println!("Found {} files to process", files.len());
        }

        let word_counts = if self.config.use_mmap {
            self.count_with_mmap(files)?
        } else {
            self.count_with_read(files)?
        };

        let sorted_counts = self.sort_results(word_counts);

        if !self.config.silent {
            self.print_stats();
        }

        Ok(sorted_counts)
    }

    // Discover files with specified extensions
    fn discover_files(&self, dir: &Path) -> Result<Vec<PathBuf>> {
        let files: Vec<PathBuf> = WalkDir::new(dir)
            .into_iter()
            .filter_map(|entry| entry.ok())
            .filter(|entry| entry.file_type().is_file())
            .filter(|entry| {
                if let Some(ext) = entry.path().extension() {
                    ext == "c" || ext == "h"
                } else {
                    false
                }
            })
            .map(|entry| entry.path().to_path_buf())
            .collect();

        Ok(files)
    }

    // Count words using memory-mapped files
    fn count_with_mmap(&self, files: Vec<PathBuf>) -> Result<AHashMap<String, u64>> {
        let (file_tx, file_rx) = bounded(self.config.num_threads * 2);
        let (result_tx, result_rx) = bounded(self.config.num_threads);

        // send files to workders
        let _producer_stats = Arc::clone(&self.stats);
        std::thread::spawn(move || {
            for file in files {
                if file_tx.send(file).is_err() {
                    break;
                }
            }
        });

        // process files
        Ok(crossbeam::scope(|s| {
            for _ in 0..self.config.num_threads {
                let rx = file_rx.clone();
                let tx = result_tx.clone();
                let stats = Arc::clone(&self.stats);

                s.spawn(move |_| {
                    let mut local_counts = AHashMap::with_capacity(1024);

                    while let Ok(file_path) = rx.recv() {
                        if let Err(e) =
                            self.process_file_mmap(&file_path, &mut local_counts, &stats)
                        {
                            eprintln!("Error processing {}: {}", file_path.display(), e);
                        }
                    }

                    let _ = tx.send(local_counts);
                });
            }

            drop(result_tx);

            // Collect all results from workers
            let all_results: Vec<AHashMap<String, u64>> = result_rx.iter().collect();

            // Merge using parallel or sequential strategy
            self.merge_results(all_results)
        })
        .unwrap())
    }

    // Process a single file using memory mapping
    fn process_file_mmap(
        &self,
        file_path: &Path,
        counts: &mut AHashMap<String, u64>,
        stats: &Stats,
    ) -> Result<()> {
        let file = File::open(file_path)
            .with_context(|| format!("Failed to open {}", file_path.display()))?;

        let mmap = unsafe { Mmap::map(&file) }
            .with_context(|| format!("Failed to mmap {}", file_path.display()))?;

        stats
            .bytes_processed
            .fetch_add(mmap.len() as u64, Ordering::Relaxed);

        self.extract_words(&mmap, counts);

        stats.files_processed.fetch_add(1, Ordering::Relaxed);
        Ok(())
    }

    // Extract words from byte buffer using optimized parsing
    fn extract_words(&self, data: &[u8], counts: &mut AHashMap<String, u64>) {
        let mut word_start = None;

        for (i, &byte) in data.iter().enumerate() {
            if is_token_char(byte) {
                if word_start.is_none() {
                    word_start = Some(i);
                }
            } else if let Some(start) = word_start {
                if let Ok(word) = std::str::from_utf8(&data[start..i]) {
                    if !word.is_empty() {
                        *counts.entry(word.to_string()).or_insert(0) += 1;
                    }
                }
                word_start = None;
            }
        }

        // End of file
        if let Some(start) = word_start {
            if let Ok(word) = std::str::from_utf8(&data[start..]) {
                if !word.is_empty() {
                    *counts.entry(word.to_string()).or_insert(0) += 1;
                }
            }
        }
    }

    // Fallback impl. using regular file reads
    fn count_with_read(&self, files: Vec<PathBuf>) -> Result<AHashMap<String, u64>> {
        let all_results: Vec<AHashMap<String, u64>> = files
            .into_par_iter()
            .map(|file| {
                let mut local_counts = AHashMap::new();
                match std::fs::read(&file) {
                    Ok(contents) => {
                        self.extract_words(&contents, &mut local_counts);
                        self.stats.files_processed.fetch_add(1, Ordering::Relaxed);
                        self.stats
                            .bytes_processed
                            .fetch_add(contents.len() as u64, Ordering::Relaxed);
                    }
                    Err(e) => eprintln!("Error reading {}: {}", file.display(), e),
                }
                local_counts
            })
            .collect();

        Ok(self.merge_results(all_results))
    }

    // Merge multiple hashmaps either sequentially or in parallel
    fn merge_results(&self, results: Vec<AHashMap<String, u64>>) -> AHashMap<String, u64> {
        if self.config.parallel_merge && results.len() > 2 {
            // Use parallel reduction for multiple results
            results.into_par_iter().reduce(
                || AHashMap::with_capacity(4096),
                |mut acc, local| {
                    for (word, count) in local {
                        *acc.entry(word).or_insert(0) += count;
                    }
                    acc
                },
            )
        } else {
            // Fall back to sequential merge
            results
                .into_iter()
                .fold(AHashMap::with_capacity(4096), |mut acc, local| {
                    for (word, count) in local {
                        *acc.entry(word).or_insert(0) += count;
                    }
                    acc
                })
        }
    }

    // Sort results by count (descending) then alphabetically (ascending)
    fn sort_results(&self, counts: AHashMap<String, u64>) -> Vec<(String, u64)> {
        let mut pairs: Vec<_> = counts.into_iter().collect();

        pairs.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

        pairs
    }

    // Print performance statistics
    fn print_stats(&self) {
        let files = self.stats.files_processed.load(Ordering::Relaxed);
        let bytes = self.stats.bytes_processed.load(Ordering::Relaxed);

        println!("Processed {} files, {} bytes", files, bytes);
    }

    // Print results in formatted table
    pub fn print_results(&self, results: &[(String, u64)]) {
        if self.config.silent {
            return;
        }

        for (word, count) in results {
            println!("{:>32} | {:>8}", word, count);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_token_char_classification() {
        assert!(is_token_char(b'a'));
        assert!(is_token_char(b'Z'));
        assert!(is_token_char(b'0'));
        assert!(is_token_char(b'_'));
        assert!(!is_token_char(b' '));
        assert!(!is_token_char(b'.'));
        assert!(!is_token_char(b'\n'));
    }

    #[test]
    fn test_word_extraction() {
        let counter = FastWordCounter::new(Config::default());
        let mut counts = AHashMap::new();

        let data = b"hello world 123 test_var";
        counter.extract_words(data, &mut counts);

        assert_eq!(counts.get("hello"), Some(&1));
        assert_eq!(counts.get("world"), Some(&1));
        assert_eq!(counts.get("123"), Some(&1));
        assert_eq!(counts.get("test_var"), Some(&1));
    }

    #[test]
    fn test_file_processing() -> Result<()> {
        let mut temp_file = NamedTempFile::new()?;
        writeln!(temp_file, "int main() {{")?;
        writeln!(temp_file, "    printf(\"hello world\");")?;
        writeln!(temp_file, "    return 0;")?;
        writeln!(temp_file, "}}")?;

        let counter = FastWordCounter::new(Config::default());
        let mut counts = AHashMap::new();
        let stats = Arc::new(Stats::default());

        counter.process_file_mmap(temp_file.path(), &mut counts, &stats)?;

        assert!(counts.contains_key("int"));
        assert!(counts.contains_key("main"));
        assert!(counts.contains_key("printf"));
        assert!(counts.contains_key("hello"));
        assert!(counts.contains_key("world"));
        assert!(counts.contains_key("return"));

        Ok(())
    }
}
