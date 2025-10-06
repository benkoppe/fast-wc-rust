#!/usr/bin/env bash

pushd ../../fast-wc-rust >/dev/null || exit

cargo bench

cp -r ./target/criterion ../compare/rust-bench/criterion

popd >/dev/null || exit
