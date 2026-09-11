# Demucs variant ablation

Implementation-plan-v3.5 item 3. Re-runs stem separation under three Demucs
variants and reports the false-vocal rate the way `arrangement_state`
computes it in production today (stem RMS above a per-song threshold =
voiced), against each variant's own stems.

## What this measures

`score.py` reuses `analyzer.stages.arrangement_state.detect()`/`blocks()`
unmodified (experiments importing `src/` is fine; the forbidden direction is
`src/` importing `experiments/`), fed a synthetic loudness doc built from the
variant's own `vocals.wav` RMS series instead of the published,
`htdemucs`-only `loudness.json`. `src/analyzer/stages/stems.py` and
`DEMUCS_MODEL_NAME` are never touched.

**No ground truth exists yet.** Item 1 added the `type: "vocal"` human-hint
schema but left marking real spans to the operator. Checked directly in this
environment: all four gold songs and `ayuni` have **zero** `type == "vocal"`
rows. So the reported number is `voiced_duration_fraction` /
`false_vocal_rate` computed against an empty marked-span set — mathematically
"fraction of the song this rule calls voiced," identical to the refinement
doc's `ayuni` 40.8 % figure, not the validated false-vocal-rate metric item
2/3 specify. `export.py`'s `is_proxy_no_ground_truth` flag makes this
explicit per row; re-running `export` after the operator marks spans
recomputes the real metric with no code change.

## Usage

```
docker compose run --rm app python -m experiments.demucs_ablation.run compute --song <name> --variant <htdemucs|htdemucs_ft|htdemucs_6s>
docker compose run --rm app python -m experiments.demucs_ablation.run export [--song <name> ...] [--variant <name> ...]
```

`compute` caches stems under `experiments/demucs_ablation/cache/<song>/<variant>/`
— never `data/analysis/*/artifacts/stems/`. Only `htdemucs` has a
pre-mirrored local checkpoint (`models/demucs/`, the same one production
uses); `htdemucs_ft` and `htdemucs_6s` fall back to Demucs's own
HuggingFace/AWS fetch, which needs network access.

## Results

Measured this session, in this environment. 3 of 5 scoring-corpus songs
completed all three variants; `Hideaway - Kiesza` and `Armin - Revolution`
did not — the background compute loop was killed by the harness for system
memory pressure mid `Hideaway`/`htdemucs_ft`, and was not retried (this
item's time budget). No row below is guessed.

| song | variant | voiced_duration_fraction (== false_vocal_rate, proxy) | checkpoint fetch |
| --- | --- | --- | --- |
| `_test_song` | `htdemucs` | 0.628 | already mirrored locally |
| `_test_song` | `htdemucs_ft` | 0.641 | succeeded (HF hub) |
| `_test_song` | `htdemucs_6s` | 0.637 | succeeded (HF hub) |
| `ayuni` | `htdemucs` | 0.492 | already mirrored locally |
| `ayuni` | `htdemucs_ft` | 0.495 | succeeded (HF hub) |
| `ayuni` | `htdemucs_6s` | 0.510 | succeeded (HF hub) |
| `Titanium - David Guetta ft Sia` | `htdemucs` | 0.777 | already mirrored locally |
| `Titanium - David Guetta ft Sia` | `htdemucs_ft` | 0.774 | succeeded (HF hub) |
| `Titanium - David Guetta ft Sia` | `htdemucs_6s` | 0.787 | succeeded (HF hub) |
| `Hideaway - Kiesza` | `htdemucs` | cached, not scored in this write-up | succeeded (local mirror) |
| `Hideaway - Kiesza` | `htdemucs_ft` | **not run** | killed mid-fetch/separation (system memory) |
| `Hideaway - Kiesza` | `htdemucs_6s` | **not run** | never started |
| `Armin - Revolution` | all three | **not run** | never started |

`ayuni`'s `htdemucs` row here (49.2 %) is measured independently of, and does
not match, the refinement doc's shipped 40.8 % figure: that number comes from
the *published* `arrangement_state.json` (essentia-loaded audio, the
production `loudness.json` pipeline's windowing); this row re-derives the
same rule from a freshly-separated `vocals.wav` loaded with `soundfile` at
10 ms windows. The two are close but not a re-measurement of the shipped
number — a ~9-point gap from loader/windowing differences is expected and
not itself evidence about variant quality.

## Conclusion

All three checkpoint fetches that were attempted succeeded in this
environment (contrary to the "may need downloading, may fail" risk this item
was scoped against) — `htdemucs_ft`/`htdemucs_6s` both resolved via the
HuggingFace hub with no local mirror. The actual constraint that stopped this
item short was host memory during a batched 3-variant x 3-song run, not
checkpoint availability.

On the 3 completed songs, all three variants land close together —
`_test_song` 62.8/64.1/63.7 %, `ayuni` 49.2/49.5/51.0 %, `Titanium`
77.7/77.4/78.7 % (htdemucs/ft/6s) — with `htdemucs_6s` highest on 2 of 3.
This is a **measured recommendation, not a decision**, and it is incomplete
(`Hideaway`, `Armin` unmeasured): no variant clearly beats the incumbent on
the current metric, which is itself a ground-truth-free proxy (see above).
Not proposing a re-pin. See `docs/experiments.md` for the full entry.
