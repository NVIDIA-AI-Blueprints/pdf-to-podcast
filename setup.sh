#!/bin/bash

set -e

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager..."
    uv_install_script="$(mktemp)"
    curl -LsSf https://astral.sh/uv/install.sh -o "$uv_install_script"
    sh "$uv_install_script"
    rm -f "$uv_install_script"

    # Add uv to path
    # The uv installer creates this env file to add uv to PATH
    if [ -f "$HOME/.local/bin/env" ]; then
        source "$HOME/.local/bin/env"
    elif [ -f "$HOME/.cargo/env" ]; then
        # Fallback: some versions install to .cargo/env
        source "$HOME/.cargo/env"
    else
        # Manual fallback: add common uv install locations to PATH
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    fi
    
    # Verify uv is now available
    if ! command -v uv &> /dev/null; then
        echo "Error: uv installation succeeded but uv is not in PATH."
        echo "Please ensure the directory containing the 'uv' binary is on your PATH (commonly ~/.local/bin or ~/.cargo/bin), then try again."
        exit 1
    fi
fi

# Create a new virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies using uv pip
uv pip install -r requirements.txt

# Install shared package in editable mode
uv pip install -e shared/

echo "UV environment setup complete!"