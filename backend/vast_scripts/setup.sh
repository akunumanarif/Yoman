#!/bin/bash
set -e

echo "=== Yoman GPU Instance Setup ==="

# Check if setup already completed successfully
if [ -f "/workspace/.setup_complete" ]; then
    echo "Wan2.2 already installed, skipping setup."
    exit 0
fi

# Install system dependencies
apt-get update && apt-get install -y git wget ffmpeg

# Clone or repair Wan2.2 repo
echo "Setting up Wan2.2 repository..."
rm -rf /workspace/Wan2.2
cd /workspace
git clone https://github.com/Wan-Video/Wan2.2.git
cd Wan2.2
pip install -r requirements.txt --no-build-isolation --ignore-installed setuptools wheel

# Download model weights (skip if already downloaded)
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

# Mark setup as complete
touch /workspace/.setup_complete
echo "=== Setup complete ==="
