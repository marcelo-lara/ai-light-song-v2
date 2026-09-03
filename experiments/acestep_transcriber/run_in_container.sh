#!/usr/bin/env bash
# Run a step inside the ACE-Step Transcriber sandbox image.
#
#   ./experiments/acestep_transcriber/run_in_container.sh python -m experiments.acestep_transcriber.run cache
#
# Build it once from the survey's research folder, where the dependency pinning
# lives (ACE-Step Transcriber needs a transformers new enough for Qwen2.5-Omni,
# which the transformers 4.44 survey sandbox is not — hence its own image):
#
#   docker build -f experiments/drop_detection/research/Dockerfile.acestep \
#                -t ai-light-song-v2-acestep:dev .
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
  ai-light-song-v2-acestep:dev "$@"
