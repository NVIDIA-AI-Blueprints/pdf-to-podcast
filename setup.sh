#!/bin/bash

set -e

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Add uv to path
    source $HOME/.local/bin/env
fi

# Create uv project in current dir
uv init 

# Add dependencies
uv add -r requirements.txt

# Install shared package in editable mode
uv pip install -e shared/

echo "UV environment setup complete!"