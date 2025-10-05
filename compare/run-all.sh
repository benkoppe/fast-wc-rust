if [[ -z "$1" ]]; then
  echo "Usage: $0 <directory>"
  exit 1
fi

DIR="$1"
echo "Comparing on directory: $DIR"

# Example logic
if [[ ! -d "$DIR" ]]; then
  echo "Error: $DIR is not a directory"
  exit 1
fi

echo "Compiling all..."
cargo build --release --manifest-path ../fast-wc-rust/Cargo.toml
../competitors/fast-cpp/compile.sh

echo "Running all..."

echo "RUST:"
../fast-wc-rust/target/release/fast-wc-rust "$DIR"

echo "C++:"
../competitors/fast-cpp/fast-wc "$DIR"
