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

echo "Compiling all..."
cargo build --release --manifest-path "$SCRIPT_DIR/../fast-wc-rust/Cargo.toml"
"$SCRIPT_DIR/../competitors/fast-cpp/compile.sh"

echo "Running all..."
echo "RUST:"
"$SCRIPT_DIR/../fast-wc-rust/target/release/fast-wc-rust" "$DIR"

echo "C++:"
"$SCRIPT_DIR/../competitors/fast-cpp/fast-wc" "$DIR"
