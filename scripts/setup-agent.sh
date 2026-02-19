#!/bin/bash

# Navigate to the maf directory
cd "$(dirname "$0")/../maf" || exit 1

# Install dependencies and create virtual environment using uv
uv sync
