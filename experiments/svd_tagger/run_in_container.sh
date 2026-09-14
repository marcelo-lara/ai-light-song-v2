#!/usr/bin/env bash
# Run a step inside the svd_tagger research sandbox image (torch 2.4 CPU +
# panns_inference).
#
#   ./experiments/svd_tagger/run_in_container.sh python -m experiments.svd_tagger.run compute --song "<song name>"
#
# Build it once from this experiment's own Dockerfile, which is where the
# checkpoint pinning is explained:
#
#   docker build -f experiments/svd_tagger/Dockerfile \
#                -t ai-light-song-v2-svd-research:dev .
#
# `data/songs` is a symlink out of the tree, so it is bind-mounted
# explicitly — same pattern as `experiments/clap/run_in_container.sh`.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SONGS="$(readlink -f "$REPO/data/songs")"

exec docker run --rm \
  -v "$REPO":/app \
  -v "$REPO/data":/data \
  -v "$SONGS":/data/songs:ro \
  -w /app \
  -e PYTHONUNBUFFERED=1 \
  ai-light-song-v2-svd-research:dev "$@"
