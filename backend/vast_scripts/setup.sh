#!/bin/bash
set -e

echo "=== Yoman GPU Instance Setup ==="

# Check if Wan2.2 is already installed (cached via volume)
if [ -d "/workspace/Wan2.2" ] && [ -d "/workspace/models/Wan2.2-Animate-14B" ]; then
    echo "Wan2.2 already installed, skipping setup."
    exit 0
fi

# Install system dependencies
apt-get update && apt-get install -y git wget ffmpeg

# Clone Wan2.2 repo
if [ ! -d "/workspace/Wan2.2" ]; then
    echo "Cloning Wan2.2 repository..."
    cd /workspace
    git clone https://github.com/Wan-Video/Wan2.2.git
    cd Wan2.2
    pip install -r requirements.txt
fi

# Download model weights
if [ ! -d "/workspace/models/Wan2.2-Animate-14B" ]; then
    echo "Downloading Wan2.2-Animate-14B model weights..."
    pip install huggingface_hub
    python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    'Wan-AI/Wan2.2-Animate-14B',
    local_dir='/workspace/models/Wan2.2-Animate-14B',
    local_dir_use_symlinks=False,
)
"
fi

echo "=== Setup complete ==="
