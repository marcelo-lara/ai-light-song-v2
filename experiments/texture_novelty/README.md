# Experiment — Texture Novelty

*(no external model or repo — classical self-similarity novelty, numpy + librosa)*

## Status

**Measured, FAILED its kill condition, kept as a lane for one operator review
pass — kill candidate.** Nothing in `src/` reads anything here. Queue entry with
the same numbers in summary form:
[`../../docs/experiments.md`](../../docs/experiments.md).

The debugger lane exists: **`2. Texture Novelty`**, under Human Hints, flask
badge, reads `reference/proposals/texture_novelty.json`.

## Why? What for?

`sections.json` has **no boundary at 48.7 s** on `Queen of Kings` where the
operator hears the drop, and its boundary F1 against operator hints is weak
across the corpus. The refinement doc (item 2) already measured that
self-similarity novelty over spectral features has **recall 0.80–1.00** against
operator hints on every gold song — the texture genuinely changes at every
operator boundary — but at **precision 0.05–0.50**: it fires 64–114 times per
song. The question this lane exists to answer:

> Does a *feature choice* exist that keeps the recall and lifts the precision
> above 0.5 — locating operator hint boundaries better than `sections.json` and
> `arrangement_state.json`?

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.texture_novelty.run compute
docker compose run --rm --no-deps app python -m experiments.texture_novelty.run export
docker compose run --rm --no-deps app python -m experiments.texture_novelty.run score
```

`compute` re-derives per-song feature matrices from `data/analysis/**` and
writes one `cache/<song>.npz`; `score` and `export` read only the cache, so
the tables reproduce on a checkout with no `data/` and no audio. Feature sets 1
and 3 are read straight from the published `fft_bands.json` /
`fft_bands.<stem>.json` (same 44100 Hz / 4096 Hann / 50 ms hop as
`src/analyzer/stages/fft_bands.py`); feature set 2's chroma and the MFCC
baseline are librosa on the mix at the same hop.

Songs lacking per-stem FFT need it first (fast, no GPU):
`docker compose run --rm app ./analyze --song "/data/songs/<song>.mp3" --stage extract-fft-bands`.

## Experiment Plan

**Method (fixed, not swept):** cosine self-similarity matrix → Foote
checkerboard novelty kernel, **1.0 s half-window** → peak-pick (local maxima
above `mean + 1·std`, ≥ 2.0 s apart). The method config is held constant; only
the feature changes, because the kill condition is about the feature.

**Feature sets, tried IN ORDER, scored separately:**

1. **raw 7-band MIX vector** from `fft_bands.json` — the measured baseline.
2. **chroma(MIX) + percussive-band weight** — librosa `chroma_cqt` on the mix
   (12-dim), L2-normalised, concatenated with the mix's upper-mid/presence/
   brilliance band weight (z-scored). **Never the harmonic-stem `hpcp.json`**
   (D6.1 below) — it reads 0.009 RMS at the `Queen of Kings` drop.
3. **per-stem band weight** — the 7 `levels` of each of `bass`/`drums`/
   `harmonic`/`vocals` `fft_bands.<stem>.json`, stacked to 28 dims.

**Cheap baselines:** mix-RMS delta (|d/dt| of a smoothed mix RMS, peak-picked);
MFCC novelty (20-dim librosa MFCC on the mix through the same SSM+checkerboard
pipeline).

**Metric:** boundary F1 @ ±1.0 s vs `reference/human/human_hints.json` block
edges (start + end of every hint, edges within 0.5 s merged) on the four gold
songs, greedy one-to-one matching. Tabulated against `sections.json` and
`arrangement_state.json` boundaries.

**Kill condition:** a feature set passes only if it lifts **precision > 0.5 at
recall ≥ 0.8** (pooled over the four gold songs).

### D6.1 (resolved during implementation)

The plan text says "chroma/HPCP on the MIX (`artifacts/essentia/hpcp.json`)…
NEVER the harmonic stem". The published `hpcp.json` **is** computed on the
harmonic stem (`generated_from.harmonic_stem` is set) — the two halves of that
sentence contradict. Resolved by honouring the intent ("on the MIX", "never the
harmonic stem"): feature set 2 computes chroma with librosa on the mix audio,
not `hpcp.json`. Recorded as a `D` in
[`../../docs/implementation-plan-v3.4.md`](../../docs/implementation-plan-v3.4.md)
item 6.

## Results evidence

Full tables in [`out/score.txt`](out/score.txt), reproduced by `run score`.
Gold set, 48 pooled human-hint block edges.

**Pooled (4 gold songs), boundary F1 @ ±1.0 s:**

| method | P | R | F1 | pred |
| --- | --- | --- | --- | --- |
| feat 1 — raw 7-band MIX vector | 0.12 | 0.19 | 0.14 | 78 |
| feat 2 — chroma(MIX) + percussive weight | 0.12 | 0.23 | 0.16 | 91 |
| feat 3 — per-stem band weight (28-dim) | 0.20 | 0.35 | 0.26 | 84 |
| baseline — mix-RMS delta | 0.15 | 0.42 | 0.22 | 137 |
| baseline — MFCC novelty | 0.21 | 0.38 | 0.27 | 85 |
| incumbent — `sections.json` | 0.31 | 0.17 | 0.22 | 26 |
| incumbent — `arrangement_state.json` | 0.14 | 0.44 | 0.22 | 145 |

**Per song, the three feature sets (F1):**

| song | feat 1 | feat 2 | feat 3 | `sections.json` | `arrangement_state` |
| --- | --- | --- | --- | --- | --- |
| `_test_song` | 0.44 | 0.29 | **0.64** | 0.00 | 0.62 |
| `Titanium` | 0.06 | 0.00 | 0.10 | **0.24** | 0.08 |
| `Hideaway` | 0.09 | 0.11 | 0.11 | **0.31** | 0.12 |
| `Armin` | 0.13 | 0.34 | 0.33 | 0.30 | 0.23 |

**Kill condition: FAIL.** No feature set clears precision > 0.5 at recall ≥ 0.8,
pooled or on any single gold song. Best pooled precision is feat 3 at **0.20**
(recall 0.35); best pooled recall among the novelty features is feat 3 at 0.35.
The one bright spot — feat 3 on `_test_song` (P 0.88, R 0.50) — does not
generalise: on the three real songs feat 3 sits at F1 0.10–0.33.

**What the numbers say.**

- The refinement doc's "recall 0.80–1.00" was measured with a much denser
  peak-picker (64–114 fires/song). This run uses a conservative fixed
  `mean+1·std` / 2.0 s-spacing picker (26–91 fires/song). Loosening it back
  toward the dense regime trades precision *down* toward 0.05 as recall rises —
  the refinement doc's own finding, reconfirmed: **there is no operating point
  on this curve that clears the bar.** Ranking peaks by magnitude was already
  shown (refinement doc) to make F1 worse, so that route is closed too.
- Per-stem features (feat 3) are the strongest of the three, consistent with
  "bass-, mid- or top-driven motion explains a boundary" — but the lift is
  small and synthetic-song-driven.
- On the two real vocal-pop songs (`Titanium`, `Hideaway`) `sections.json` is
  the best method in the table. Texture novelty adds nothing there.

## Conclusion

**Killed on the metric.** Every feature set fails precision > 0.5 at recall ≥
0.8, and the failure is structural, not a tuning gap: the texture-change signal
is real everywhere (which is exactly why precision cannot rise — it changes at
non-boundaries just as often). This reconfirms the refinement doc's own
measurement rather than overturning it.

Per the plan, the lane is **kept for one operator review pass** so the proposal
blocks can be auditioned against Human Hints on the waveform, then removed by
Recipe B if the operator agrees. **Do not tune the peak-picker to manufacture a
pass.** If anything here is worth carrying forward it is the per-stem feature
direction (feat 3), and that belongs to Structural vs Micro (item 8), not here.

## Reach test

Time-bearing output → `reference/proposals/texture_novelty.json`, rendered as
the **`2. Texture Novelty`** lane. Not promoted, no top-level file, nothing in
`src/` or `mcp/` reads it — and on this result, not a promotion candidate.
