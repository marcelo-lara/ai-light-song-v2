# Experiment — Rhythm Vocal Onsets

## Status

**OPEN.** Candidate producer for `sections.json`'s `rhythm.vocals` field
(`docs/product-refinement-v3.6.md` item 6, method (c)). Scores are
**provisional** until item 4's `segments.seed.json` is operator-reviewed.

Debugger lane: **`Rhythm Vocal Onsets`**, flask badge, reads
`reference/proposals/rhythm_vocal_onsets.json`.

## Method

Word onset times from `experiments.acestep_transcriber.whisper_baseline`
(whisper-large-v3 over the vocal stem, item 3) inside a segment span: dominant
inter-onset interval / local beat period -> nearest subdivision, same
vocabulary and confidence rule as `rhythm_drum_ioi`
(`experiments/rhythm_energy_common.py`). Also writes `onsets_per_beat`
(word count / beats-in-span).

**Not autocorrelation** — unlike `rhythm_stem_autocorr`, this uses actual
onset *times* (a syllable-onset proxy), which is what a lyric transcript
gives for free once it has word timestamps.

## How to run it — `compute` needs the ACE-Step sandbox image

`compute` is **never** run through the normal `./experiment` queue path — the
`app` image does not have `faster_whisper`. `queue.toml`'s row for this
experiment names an `image` the runner never honors (same convention as
`svd_tagger`), so it always shows `skipped(needs image ...)` in the queue log.
Build the sandbox image once (see
`experiments/drop_detection/research/Dockerfile.acestep`, `-t
ai-light-song-v2-acestep:dev`) if it does not already exist from item 3, then:

```bash
./experiments/acestep_transcriber/run_in_container.sh python -m experiments.rhythm_vocal_onsets.run compute --song "<name>"
docker compose run --rm --no-deps app python -m experiments.rhythm_vocal_onsets.run export --song "<name>"
docker compose run --rm --no-deps app python -m experiments.rhythm_vocal_onsets.run score
```

`export` and `score` need no GPU (they read the whisper cache `compute`
wrote) and run in the normal `app` image.

Run on the 4 segment songs plus `Armin - Revolution`.

## Results

Not yet run — placeholder. Real numbers land in `out/score.txt` and this
section, and in `docs/experiments.md`, after the orchestrator runs
compute/export/score.

## Reach test

Candidate for `sections.json`'s `rhythm.vocals` field (fused by confidence
alongside `rhythm_drum_ioi`'s `(a)` and `rhythm_stem_autocorr`'s `(b)`). Not
yet promoted.
