#!/usr/bin/env bash

C_FILES=${1:-50}
H_FILES=${2:-30}

python3 generate-large-files.py -c "$C_FILES" -H "$H_FILES"

../run-all.sh ./generated_input/
