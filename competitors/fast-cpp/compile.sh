#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

c++ -O3 -std=c++20 \
  "$SCRIPT_DIR/fast-wc.cpp" \
  "$SCRIPT_DIR/utils.cpp" \
  -lpthread -lstdc++fs \
  -o "$SCRIPT_DIR/fast-wc"
