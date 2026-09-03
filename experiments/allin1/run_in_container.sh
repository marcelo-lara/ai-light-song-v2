#!/usr/bin/env bash
# Run the GPU step inside the allin1 sandbox image.
#
#   ./experiments/allin1/run_in_container.sh python -m experiments.allin1.run cache
#
# The image is built from the sibling experiment's Dockerfile, which is the one
# place the natten 0.15 / torch 2.1 pinning is explained:
#
#   docker build -f experiments/drop_detection/research/Dockerfile.allin1 \
#                -t ai-light-song-v2-allin1:dev .
#
# `data/songs` is a symlink out of the tree, so it is bind-mounted explicitly
# the way docker-compose does it.
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
  ai-light-song-v2-allin1:dev "$@"
