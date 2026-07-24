#!/usr/bin/env bash
# validate_inference/run.sh
#
# WHEN TO RUN THIS SCRIPT
# ━━━━━━━━━━━━━━━━━━━━━━━
# This script is NOT part of the fast smoke-test CI (edge/ pytest suite).
# The edge CI image intentionally excludes ultralytics to keep the Docker
# image small (~50 MB vs >1 GB with PyTorch).
#
# Run this validation:
#
#   1. BEFORE RELEASING A NEW MODEL CHECKPOINT (yolo_retail.pt).
#      Each time a new checkpoint is trained or sourced, run:
#
#        ./validate_inference/run.sh --model /path/to/yolo_retail.pt
#
#      This confirms the checkpoint loads, detects people with confidence >0.5,
#      and that ByteTrack tracking produces stable track IDs.
#
#   2. WHEN CHANGING INFERENCE CODE IN edge/gateway.py (_yolo_detections,
#      _yolo_track_loop, or any ByteTrack parameters).
#      The fast CI catches unit-level regressions; this script catches
#      model-level regressions (e.g. class mapping changes, tracker config).
#
#   3. PERIODICALLY (recommended: quarterly), even if no checkpoint changed,
#      to guard against PyTorch/ultralytics version regressions.
#
# HOW TO RUN
# ━━━━━━━━━━
# Option A — local Python (Python ≥ 3.9):
#
#   pip install -r validate_inference/requirements.txt
#   ./validate_inference/run.sh [--model /path/to/yolo_retail.pt]
#
# Option B — isolated Docker environment (no local Python deps needed):
#
#   docker build -f validate_inference/Dockerfile -t traxia-validate validate_inference/
#   docker run --rm traxia-validate [--model /model/yolo_retail.pt] \
#              [-v /host/path/to/yolo_retail.pt:/model/yolo_retail.pt:ro]
#
# CI INTEGRATION
# ━━━━━━━━━━━━━━
# If you want this in CI as a separate slower job (not the per-commit smoke test):
#
#   # In your CI pipeline (GitHub Actions example):
#   # Trigger: manual workflow_dispatch OR on new checkpoint upload to R2
#   - name: Validate YOLO inference
#     run: |
#       pip install -r validate_inference/requirements.txt
#       ./validate_inference/run.sh --model ${{ inputs.checkpoint_path }}
#
# WHAT THIS DOES NOT REPLACE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# - edge/tests/ (fast unit + integration tests, run on every commit)
# - end-to-end tests with a real RTSP stream (mediamtx fixture in conftest.py)
#   Those use the STUB model and test the capture/queue/flush pipeline.
#   This script adds real inference to that coverage.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MODEL="${1:---model}"
MODEL_PATH="${2:-yolov8n.pt}"
if [[ "$MODEL" != "--model" ]]; then
    # called as: ./run.sh /path/to/model.pt
    MODEL_PATH="$MODEL"
fi

echo ""
echo "=== Traxia Edge YOLO Inference Validation ==="
echo "Running from: $REPO_ROOT"
echo ""

cd "$REPO_ROOT"

echo "Step 1 — Inference validation (3 real images, person class, conf > 0.50)"
python3 validate_inference/validate_yolo.py --model "$MODEL_PATH"
echo ""

echo "Step 2 — End-to-end pipeline (inference → queue → flush → XY bounds)"
python3 validate_inference/test_pipeline_e2e.py --model "$MODEL_PATH"
echo ""

echo "=== ALL VALIDATION STEPS PASSED ==="
echo "Update model_manager.py docstring with today's date and the model path used."
