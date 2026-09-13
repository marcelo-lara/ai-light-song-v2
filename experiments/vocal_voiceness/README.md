# Vocal voiceness — vibrato + portamento + sibilance timbre discriminator

*(no external model — classical DSP: pitch/vibrato/portamento/sibilance features)*

## Status

**OPEN — built and running, kill condition unevaluable until item 1's ground
truth exists.** v3.5 item 4. `compute`/`export`/`score` all run green on
`_test_song`, `ayuni`, and the three remaining gold songs
(`Hideaway - Kiesza`, `Armin - Revolution`, `Titanium - David Guetta ft Sia`).
Debugger lane `4. Vocal Voiceness` wired in, under Human Hints. No song in
this environment carries `type: "vocal"` ground truth (same finding as item
3's `demucs_ablation`), so the kill condition — "does not cut the false-vocal
rate on `ayuni` below the `arrangement_state` incumbent at a matched budget" —
cannot actually be evaluated yet. `score.py` reports an honest proxy instead
(see below), flagged `is_proxy_no_ground_truth` per row.

## Why? What for?

Refinement doc question: can pitch-contour and spectral cues (vibrato width,
portamento glide, sibilance bursts) separate a sung phrase from a
pitched-instrument leak in the same vocal stem, where a level gate cannot?
`arrangement_state`'s stem-RMS threshold reports `vocals` present 40.8% of
`ayuni` — the false-vocal question items 3-7 all chase from different angles.

## Method

Three per-50ms-frame cues (`features.py`), combined by noisy-OR (`model.py`),
plus a pitch-continuity bridge over `vocal_phrases`' documented
`sustained_notes` gap:

| Cue | Signal | Source |
| --- | --- | --- |
| vibrato | depth (cents, detrended f0 residual std) x rate (3-8Hz zero-crossing) | pYIN f0, reused from `vocal_phrases`'s cache (fresh compute as fallback) |
| portamento | glide slope (200-2000 cents/s) x linear-fit smoothness (R²) | same f0 track |
| sibilance | `presence`(2.5-6kHz)+`brilliance`(6-16kHz) band levels, weighted toward `transient_strength` (burst character over sustained brightness) | published `artifacts/essentia/fft_bands.vocals.json` — no new FFT |

`voiceness = 1 - Π(1 - wᵢ·cueᵢ)` (noisy-OR, not a weighted average) — a single
strong cue (sibilance especially, "the cue no pitched instrument can fake" per
the refinement doc) should carry a frame, not get diluted by two other cues
sitting near zero at that same instant. Weights: sibilance 0.80, vibrato 0.55,
portamento 0.35 — a documented judgement call, **not fit to any ground
truth** (none exists). `confidence` = `|voiceness - 0.5| × 2`, an honest
decision-margin heuristic, not a calibrated probability.

**None of the three cue thresholds are corpus-tuned.** Vibrato/portamento
bands come from the general vibrato-acoustics literature's typical singing
range, not fit against this corpus — `features.py`'s module docstring says so
explicitly.

## The `sustained_notes` bridge

`vocal_phrases.detector.derive_phrases` gates on RMS-ratio hysteresis alone: a
held note's own amplitude decay can dip the ratio below the OFF threshold
mid-note, fragmenting one sustained tone into two runs before either reaches
the 1.5s sustain minimum (documented in `vocal_phrases/README.md` as "A real,
documented limitation," confirmed on `_test_song`'s drop-build hold).
`model.py`'s `derive_vocal_phrases` recomputes the same word-level hysteresis
split, then bridges any gap ≤0.6s where the f0 just before and after sits
within 60 cents (`vocal_phrases`' own tolerance constant) — using pYIN samples
*inside* the gap as direct evidence when pYIN reports any pitch there.

**Bridge fires, and measurably adds value beyond the stock 0.5s breath
merge** — but the fix is not yet visible in `sustained_notes` counts:

| song | word-level gaps found | bridged | bridged gaps > 0.5s (would NOT have merged under vocal_phrases' own breath threshold) | sustained_notes (bridged) | sustained_notes (`vocal_phrases`, unbridged) |
| --- | --- | --- | --- | --- | --- |
| `_test_song` | 28 runs → 22 after bridge | 6 | 0 | 0 | 0 |
| `ayuni` | — | 37 | **2** (0.557s, 0.592s, both pitch-continuous within 5-0 cents) | 0 | 0 |

`ayuni` is concrete evidence the bridge does something `vocal_phrases`' own
0.5s breath-merge does not — two gaps over half a second, pitch-continuous
within a few cents, only merged by this item's f0-based check. **But
`sustained_notes` is still 0 on both songs after bridging.** Root cause is a
*different* limit than the one this item targeted: the sustain scan's own
pitch-stability gate (60 cents held for ≥1.5s, unchanged from
`vocal_phrases`) is a separate condition from the amplitude-gate fragmentation
this item fixes — a phrase can now survive the amplitude dip intact and still
fail the sustain scan's own tolerance/duration requirement. Not solved by this
item; reported honestly rather than claimed.

## Results evidence

Scored against `voiceness_common`'s three incumbents (`arrangement_state`,
`vocal_phrases`, mix-RMS baseline) via the shared scorer, matched-budget
(`bounds_per_min` reported beside every rate, never compared alone).

**Rescored 2026-09-13** — v3.5 corpus rebuild, three-class scorer, the 5 songs
declared in `voiceness_common/vocal_ground_truth.json`. Full output:
[`out/score.txt`](out/score.txt). frame_acc / false_vocal_rate / bounds/min on
the two songs that declare negatives (the other three cannot rank detectors):

| song | vocal_voiceness | arrangement_state | vocal_phrases | mix_rms_baseline |
| --- | --- | --- | --- | --- |
| `ayuni` | 0.8708 / 0.0323 / 53.0 | 0.9042 / 0.0891 / 6.6 | 0.7038 / 0.1514 / 53.0 | 0.3263 / 0.6585 / 69.9 |
| `Cinderella - Ella Lee` | 0.6450 / 0.0176 / 37.0 | 0.9369 / 0.0040 / 5.7 | 0.5022 / 0.1347 / 37.0 | 0.5143 / 0.4163 / 73.1 |

`ayuni` reproduced its pre-rebuild row exactly; `Cinderella` moved 0.6760 →
0.6450 against the repaired class map. Promoted whisperX scores 0.9881 / 0.8134
on the same two songs.

## Usage

```bash
docker compose run --rm app python -m experiments.vocal_voiceness.run compute --song <name>
docker compose run --rm app python -m experiments.vocal_voiceness.run export --song <name>
docker compose run --rm app python -m experiments.vocal_voiceness.run score [--song <name> ...]
```

`compute` computes the three cues and caches them under
`experiments/vocal_voiceness/cache/`. `export` combines them and writes
`reference/proposals/vocal_voiceness.json` via `voiceness_common.schema`.
`score` (no `--song` = the 5-song scoring corpus) writes `out/score.txt`.

## Conclusion

Built, green end-to-end on all 5 scoring-corpus songs. The pitch-continuity
bridge is demonstrably real — `ayuni` shows two gaps merged that the stock
`vocal_phrases` breath threshold would not have caught — but has not yet
produced a single `sustained_notes` row on any tested song, a separate,
unfixed gap in the sustain scan's own pitch-tolerance criterion.

Against real ground truth it trails both incumbents on frame accuracy on both
discriminating songs (`ayuni` 0.8708 vs RMS 0.9042 and whisperX 0.9881;
`Cinderella` 0.6450 vs 0.9369 / 0.8134), at `vocal_phrases`' word-level firing
budget. Its lasting value is the **sibilance cue**, already promoted as
`vocals_phrase[].sibilance` — see `docs/experiments.md` for the per-cue AUCs.
The noisy-OR of all three cues is not a promotion candidate.
