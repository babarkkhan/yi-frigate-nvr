#!/usr/bin/env bash
# Exports a YOLOv9-tiny ONNX model at 320x320 for Frigate's onnx detector.
# Frigate does not ship a model for ONNX - it has to be built once.
# Run from the repo root, inside WSL, after Docker is working.
set -euo pipefail

OUT_DIR="$(pwd)/services/nvr/config/model_cache"
CTX="$(mktemp -d)"   # empty build context - the repo has 34MB of firmware backups
mkdir -p "$OUT_DIR"

trap 'rm -rf "$CTX"' EXIT
echo "==> exporting yolov9-t at 320x320 (this takes several minutes)"
set -o pipefail
docker build "$CTX" --build-arg MODEL_SIZE=t --build-arg IMG_SIZE=320 \
  --output "$OUT_DIR" -f- <<'DOCKERFILE'
FROM python:3.11 AS build
RUN apt-get update && apt-get install --no-install-recommends -y cmake libgl1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /bin/
WORKDIR /yolov9
ADD https://github.com/WongKinYiu/yolov9.git .
RUN uv pip install --system -r requirements.txt
RUN uv pip install --system onnx==1.18.0 onnxruntime onnx-simplifier==0.4.* onnxscript
ARG MODEL_SIZE
ARG IMG_SIZE
ADD https://github.com/WongKinYiu/yolov9/releases/download/v0.1/yolov9-${MODEL_SIZE}-converted.pt yolov9-${MODEL_SIZE}.pt
# PyTorch >=2.6 defaults torch.load to weights_only=True, which rejects
# yolov9's pickled DetectionModel. This env var restores the old behaviour.
# Safe here: the checkpoint comes from the official yolov9 release.
RUN TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 python3 export.py --weights ./yolov9-${MODEL_SIZE}.pt --imgsz ${IMG_SIZE} --simplify --include onnx
FROM scratch
ARG MODEL_SIZE
COPY --from=build /yolov9/yolov9-${MODEL_SIZE}.onnx /yolo.onnx
DOCKERFILE

echo
if [ -f "$OUT_DIR/yolo.onnx" ]; then
  echo "==> built: $OUT_DIR/yolo.onnx  ($(du -h "$OUT_DIR/yolo.onnx" | cut -f1))"
  echo "Now edit services/nvr/config/config.yml:"
  echo "  - comment out the detectors: cpu1: block"
  echo "  - uncomment the detectors: onnx: and model: blocks"
  echo "  - uncomment hwaccel_args: preset-nvidia"
  echo "Then: docker compose restart frigate"
else
  echo "==> build produced no yolo.onnx - check the output above"
  exit 1
fi
