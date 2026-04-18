#!/bin/bash
set -e

echo "=== Yoman GPU Instance Setup ==="

# Check if setup already completed successfully
if [ -f "/workspace/.setup_complete" ]; then
    echo "Wan2.2 already installed, skipping setup."
    exit 0
fi

# Fix NVIDIA apt key (move from legacy keyring to modern format)
if apt-key list 2>/dev/null | grep -q "nvidia\|cuda" 2>/dev/null; then
    apt-key export 7FA2AF80 2>/dev/null | gpg --dearmour -o /etc/apt/trusted.gpg.d/nvidia.gpg 2>/dev/null || true
fi

# Install system dependencies
apt-get update && apt-get install -y git wget ffmpeg

# Clone or repair Wan2.2 repo
echo "Setting up Wan2.2 repository..."
rm -rf /workspace/Wan2.2
cd /workspace
git clone https://github.com/Wan-Video/Wan2.2.git
cd Wan2.2
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --no-build-isolation

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
