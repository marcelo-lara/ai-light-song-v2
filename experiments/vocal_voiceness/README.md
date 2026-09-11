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

**No ground truth exists yet** — checked directly, same finding as item 3:
every song in the scoring corpus (`_test_song`, `ayuni`, and the three
remaining gold songs) has zero `type == "vocal"` rows in
`reference/human/human_hints.json` in this environment. So
`false_vocal_rate` against an empty marked-span set is mathematically
"fraction of frames this candidate calls voiced" — an honest proxy, not the
validated metric, flagged `is_proxy_no_ground_truth` per row in
`out/score.txt`. Re-running `score` after the operator marks spans
recomputes the real number with no code change.

Full 5-song scoring corpus (proxy numbers, 0 marked spans on every song),
`false_vocal_rate` (proxy) / `bounds_per_min`:

| song | vocal_voiceness | arrangement_state | vocal_phrases | mix_rms_baseline |
| --- | --- | --- | --- | --- |
| `_test_song` | 0.1454 / 22.74 | 0.3787 / 10.34 | 0.3830 / 22.74 | 0.9535 / 6.20 |
| `Hideaway - Kiesza` | 0.2219 / 54.36 | 0.8343 / 6.68 | 0.3182 / 54.84 | 0.8401 / 39.10 |
| `Armin - Revolution` | 0.0564 / 55.68 | 0.6418 / 5.57 | 0.2314 / 55.68 | 0.9794 / 10.52 |
| `Titanium - David Guetta ft Sia` | 0.2930 / 45.97 | 0.7143 / 5.16 | 0.2868 / 46.48 | 0.9602 / 18.59 |
| `ayuni` | 0.1800 / 53.19 | 0.4082 / 6.56 | 0.2449 / 53.19 | 0.8765 / 70.67 |
| **aggregate avg** | **0.1793 / 46.39** | 0.5955 / 6.86 | 0.2929 / 46.59 | 0.9219 / 29.02 |

Full output: [`out/score.txt`](out/score.txt) (measured this session, all 5
scoring-corpus songs).

**This lower proxy false_vocal_rate is not evidence of a real win.** Every
number above is "fraction of frames called voiced" with no ground truth to
check it against — a candidate that fires *less* often scores better on this
proxy regardless of whether its calls are actually correct. The kill
condition genuinely cannot be evaluated until item 1's `type: "vocal"` hints
exist.

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

On the plan's own kill-condition song, `ayuni`'s proxy `false_vocal_rate` is
lower for `vocal_voiceness` (0.180) than `arrangement_state` (0.408) — on the
literal proxy number this "beats the incumbent." **This is not a pass of the
kill condition**: with zero `type: "vocal"` ground truth on every scoring-corpus
song, `false_vocal_rate` here is mathematically "fraction of frames called
voiced," and `vocal_voiceness` calling fewer frames voiced is not evidence
those calls are more *correct* — a candidate that fires less can always win
this proxy regardless of accuracy. Aggregate across all 5 songs:
`vocal_voiceness` 0.179 vs `arrangement_state` 0.596, `vocal_phrases` 0.293,
mix-RMS 0.922 — the ranking is consistent song to song, which is at least
evidence the candidate isn't wildly unstable, but stability of a
ground-truth-free proxy is not the same claim as the kill condition. **Not a
promotion candidate on current evidence**, and the kill condition is
explicitly unevaluable, not passed or failed. Next step is the same one item
3 named: mark `type: "vocal"` spans on `ayuni` (and ideally a second leaky
track), then re-run `score` with no code change.
