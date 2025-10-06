#!/usr/bin/env bash

if [[ -z "$1" ]]; then
  echo "Usage: $0 <directory>"
  exit 1
fi

# Resolve this script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$1"

echo "Comparing on directory: $DIR"

if [[ ! -d "$DIR" ]]; then
  echo "Error: $DIR is not a directory"
  exit 1
fi

echo "Building..."
cargo build --release --manifest-path "$SCRIPT_DIR/../fast-wc-rust/Cargo.toml"
"$SCRIPT_DIR/../competitors/fast-cpp/compile.sh"

echo
echo "Benchmarking with hyperfine..."

# Get number of CPU cores for fair comparison
NCPUS=$(nproc)

hyperfine \
  --warmup 2 \
  --runs 10 \
  --parameter-list threads ${NCPUS} \
  --parameter-list blocks 1,2,4,8 \
  --parameter-list parallel "-p," \
  "$SCRIPT_DIR/../fast-wc-rust/target/release/fast-wc-rust --threads {threads} {parallel} --silent $DIR" \
  "$SCRIPT_DIR/../competitors/fast-cpp/fast-wc -n{threads} -b{blocks} {parallel} -s $DIR"
