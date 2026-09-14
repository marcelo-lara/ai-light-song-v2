"""whisperx_vad — whisperX's VAD front-end as its own pipeline service.

Promoted out of `experiments/whisperx_vad/` (v3.6 item 2; the research phase
that produced the promotion decision is `docs/archive/experiments_promoted.md`
"WhisperX VAD"). This is a real pipeline stage, structured like `mcp/` — its
own top-level directory, its own `Dockerfile`, its own Compose service
(`whisperx`) — because whisperX needs `torch~=2.8.0`, incompatible with the
`app` image's `torch==2.1.2`/`natten==0.15.1+torch210cu121` pin.

Unlike `experiments/`, this module MAY import from `src/` (the experiment
sandbox rule — `src/` never imports `experiments/` — does not apply to a
promoted module; see `paths.py`).

Run via `docker compose run --rm whisperx --song <path>` or `--all-songs`,
never directly on the host — Docker only (CLAUDE.md).
"""
