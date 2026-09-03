#!/usr/bin/env bash
# Run a step inside the VocalParse sandbox image.
#
#   ./experiments/vocalparse/run_in_container.sh python -m experiments.vocalparse.run cache
#
# Build it once from the survey's research folder, where the dependency pinning
# lives (VocalParse pulls torch cu124 + the `vocalparse` package, which conflict
# with the transformers 4.44 sandbox — hence its own image):
#
#   docker build -f experiments/drop_detection/research/Dockerfile.vocalparse \
#                -t ai-light-song-v2-vocalparse:dev .
#
# `data/songs` is a symlink out of the tree, so it is bind-mounted explicitly.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SONGS="$(readlink -f "$REPO/data/songs")"

exec docker run --rm \
  -v "$REPO":/app \
  -v "$REPO/data":/data \
  -v "$SONGS":/data/songs:ro \
  -w /app \
  -e HF_HOME=/app/models/hf \
  -e PYTHONUNBUFFERED=1 \
  ai-light-song-v2-vocalparse:dev "$@"
