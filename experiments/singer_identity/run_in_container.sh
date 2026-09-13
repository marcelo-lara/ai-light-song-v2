#!/usr/bin/env bash
# Run a step inside the singer_identity research sandbox image (base
# CUDA torch + speechbrain + scikit-learn).
#
#   ./experiments/singer_identity/run_in_container.sh python -m experiments.singer_identity.run compute --song "<song name>"
#
# Build it once from this experiment's own Dockerfile, which is where the
# checkpoint pinning is explained:
#
#   docker build -f experiments/singer_identity/Dockerfile \
#                -t ai-light-song-v2-singer-identity-research:dev .
#
# `data/songs` is a symlink out of the tree, so it is bind-mounted
# explicitly — same pattern as `experiments/whisperx_vad/run_in_container.sh`.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SONGS="$(readlink -f "$REPO/data/songs")"

exec docker run --rm \
  -v "$REPO":/app \
  -v "$REPO/data":/data \
  -v "$SONGS":/data/songs:ro \
  -w /app \
  -e PYTHONUNBUFFERED=1 \
  ai-light-song-v2-singer-identity-research:dev "$@"
