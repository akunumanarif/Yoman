#!/bin/bash
set -e

# Arguments
IMAGE_PATH="${1:?Usage: inference.sh <image_path> <video_path> <output_dir> <resolution>}"
VIDEO_PATH="${2:?Missing video_path}"
OUTPUT_DIR="${3:?Missing output_dir}"
RESOLUTION="${4:-720}"

echo "=== Yoman Inference ==="
echo "Image: $IMAGE_PATH"
echo "Video: $VIDEO_PATH"
echo "Output: $OUTPUT_DIR"
echo "Resolution: ${RESOLUTION}p"

# Set resolution area
if [ "$RESOLUTION" = "480" ]; then
    RES_AREA="640 480"
else
    RES_AREA="1280 720"
fi

cd /workspace/Wan2.2

# Step 1: Preprocessing
echo "=== Step 1: Preprocessing ==="
mkdir -p "$OUTPUT_DIR/processed"

python ./wan/modules/animate/preprocess/preprocess_data.py \
    --ckpt_path /workspace/models/Wan2.2-Animate-14B/process_checkpoint \
    --video_path "$VIDEO_PATH" \
    --refer_path "$IMAGE_PATH" \
    --save_path "$OUTPUT_DIR/processed" \
    --resolution_area $RES_AREA \
    --retarget_flag \
    --use_flux

# Step 2: Inference
echo "=== Step 2: Inference ==="
python generate.py \
    --task animate-14B \
    --ckpt_dir /workspace/models/Wan2.2-Animate-14B/ \
    --src_root_path "$OUTPUT_DIR/processed/" \
    --refert_num 1 \
    --offload_model True \
    --convert_model_dtype \
    --save_file "$OUTPUT_DIR/result.mp4"

# Mark completion
touch "$OUTPUT_DIR/DONE"

echo "=== Inference complete ==="
echo "Result saved to: $OUTPUT_DIR/result.mp4"
