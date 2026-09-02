#!/usr/bin/env bash
# Run a research command inside one of the two sandbox images.
#
#   ./run_in_container.sh [--allin1] python -m experiments.drop_detection.research.run ...
#
# `data/songs` in the repo is a symlink out of the tree, so it is bind-mounted
# explicitly the way docker-compose does it.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SONGS="$(readlink -f "$REPO/data/songs")"
IMAGE=ai-light-song-v2-research:dev

if [[ "${1:-}" == "--allin1" ]]; then
  IMAGE=ai-light-song-v2-allin1:dev
  shift
fi

exec docker run --rm --gpus all \
  -v "$REPO":/app \
  -v "$REPO/data":/data \
  -v "$SONGS":/data/songs:ro \
  -w /app \
  -e HF_HOME=/app/models/hf \
  -e PYTHONUNBUFFERED=1 \
  "$IMAGE" "$@"
