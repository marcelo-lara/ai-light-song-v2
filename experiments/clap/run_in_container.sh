#!/usr/bin/env bash
# Run a step inside the research sandbox image (transformers / torch 2.13).
#
#   ./experiments/clap/run_in_container.sh python -m experiments.clap.run cache
#
# Build it once from the sibling experiment's Dockerfile, which is where the
# dependency pinning is explained:
#
#   docker build -f experiments/drop_detection/research/Dockerfile \
#                -t ai-light-song-v2-research:dev .
#
# `data/songs` is a symlink out of the tree, so it is bind-mounted explicitly.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SONGS="$(readlink -f "$REPO/data/songs")"

exec docker run --rm --gpus all \
  -v "$REPO":/app \
  -v "$REPO/data":/data \
  -v "$SONGS":/data/songs:ro \
  -w /app \
  -e HF_HOME=/app/models/hf \
  -e PYTHONUNBUFFERED=1 \
  ai-light-song-v2-research:dev "$@"
