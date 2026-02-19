#!/bin/bash

# Navigate to the maf directory
cd "$(dirname "$0")/../maf" || exit 1

# Run the maf using uv
uv run src/main.py
