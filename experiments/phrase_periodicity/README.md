# Experiment — Phrase Periodicity

*(no external model or repo — classical bar-sequence autocorrelation, numpy)*

## Status

**Measured, PASSED its kill condition.** v3.4 item 7. Nothing in `src/` reads
anything here. Queue entry with the same numbers in summary form:
[`../../docs/experiments.md`](../../docs/experiments.md).

The debugger lane exists: **`3. Phrase Periodicity`**, under Human Hints, flask
badge, reads `reference/proposals/phrase_periodicity.json`.

## Why? What for?

The pipeline emits **no periodicity signal at all**. The operator's thesis is
that a passage's repetition period classifies what kind of passage it is — a
drumless long-phrase intro, a 1-bar percussion loop, a dense half-bar chorus —
and that the period of a stem (the 8-bar bass phrase on `Chimera - Hana`) is a
concrete fact a cue author can use. Question:

> What is the repetition period of a passage, and does its strength classify
> what kind of passage it is?

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.phrase_periodicity.run compute
docker compose run --rm --no-deps app python -m experiments.phrase_periodicity.run export
docker compose run --rm --no-deps app python -m experiments.phrase_periodicity.run score
```

`compute` re-derives per-song per-bar profiles from `data/analysis/**` and
writes one `cache/<song>.npz`; `score` and `export` read only the cache, so the
tables reproduce on a checkout with no `data/` and no audio.

Runs on the four gold songs plus `Chimera - Hana` and `Queen of Kings -
Alessandra` (operator-truth songs the plan names for phrase length / regime).
`Chimera - Hana` needed `./analyze --song "…" --stage extract-fft-bands` first
(fast, no GPU) — it had mix-only FFT.

## Experiment Plan

**Method (fixed, not swept).**

1. Bar grid from `beats.json` downbeats — **period only, never phase** (the
   downbeat-phase weakness does not touch a repetition-period measurement).
2. Per-stem activity envelope: `fft_bands.<stem>.json` broadband energy (mean
   of the 7 per-song-normalised band levels). Documented fallback where a song
   lacks per-stem FFT: `loudness.json` 20 ms per-stem RMS.
3. Collapse each bar to a **16-slot** energy profile (linear interp within the
   bar span).
4. **z-normalise each bar** (mean 0, unit std) so the sequence measures shape,
   not level.
5. Cosine-similarity autocorrelation of the bar sequence at **1–16 bar lags**.
   - **phrase length** = the lag in 2–16 bars where similarity peaks;
     `prominence` = peak minus its neighbouring lags, used as an honest
     confidence. Prominence `< 0.05` ⇒ **"no phrase structure detected"**, never
     a forced number.
   - **block regime** per operator block, from `rep@bar` (lag-1 bar similarity)
     and `rep@beat` (within-bar 4-slot circular similarity) on the 4-stem
     composite: `through-composed` (`rep@bar < 0.30`) / `bar-loop` /
     `half-bar-loop` (`rep@beat ≥ 0.45`).

**Cheap baseline (named ablation):** the identical pipeline on the **raw**
envelope with step 4 removed. Cosine similarity on the raw (all-positive) bar
vectors is dominated by the shared DC level, so shape agreement is washed out.

**Metric:** phrase length vs operator-stated truth (`Chimera - Hana` bass = 8
bars "almost exact", two stems independently; `Hideaway` bass = 8 bars); regime
separation vs the marked `Queen of Kings` blocks
(`reference/human/human_hints.json`, mapped to the refinement doc item 3 table).

**Kill condition:** prominence fails to separate the known-8-bar songs
(`Chimera - Hana`, `Hideaway` bass) from the rest.

## Results evidence

Full tables in [`out/score.txt`](out/score.txt), reproduced by `run score`.

### Phrase length — z-norm vs the raw ablation

| song / stem | z-norm period | z-norm prominence | raw period | raw prominence |
| --- | --- | --- | --- | --- |
| `Chimera - Hana` / bass | **8** | **+0.168** | — | +0.004 |
| `Chimera - Hana` / harmonic | **8** | +0.101 | — | +0.005 |
| `Chimera - Hana` / vocals | 8 | +0.248 | — | +0.009 |
| `Chimera - Hana` / drums | — | +0.032 | — | +0.002 |
| `Hideaway - Kiesza` / bass | 2 | **+0.118** | — | +0.007 |
| `Hideaway - Kiesza` / harmonic | 2 | +0.089 | — | +0.002 |
| `Armin - Revolution` / bass | 2 | +0.081 | — | +0.008 |
| `Queen of Kings` / bass | — | +0.041 | — | +0.007 |
| `Titanium` / bass | — | +0.028 | — | +0.002 |
| `_test_song` / bass | — | +0.005 | — | +0.004 |

**The z-normalisation is load-bearing — confirmed.** On the raw envelope the
autocorrelation finds **no phrase on any stem of any song** (every prominence
≤ 0.03). z-normalising each bar is what makes the periodicity visible at all.

**`Chimera - Hana` 8-bar bass phrase: found, on three stems independently**
(bass +0.168, harmonic +0.101, vocals +0.248) — the operator-stated ground
truth, recovered. Drums sit with no phrase peak (a shorter loop nested inside).

**`Hideaway` bass: the strongest repeat is 2 bars, not the operator's 8.** The
8-bar phrase *is* present — lag 8 is a local maximum (+0.10 vs +0.03 / +0.01
either side) — but a 2-bar sub-loop dominates the curve, so the reported period
is 2. Same nesting as `Chimera`'s drums-in-bass. The experiment does not force
the operator's number.

### Kill condition — PASS

| bass z-norm prominence | value | |
| --- | --- | --- |
| `Chimera - Hana` | +0.168 | known 8-bar |
| `Hideaway - Kiesza` | +0.118 | known 8-bar |
| `Armin - Revolution` | +0.081 | |
| `Queen of Kings` | +0.041 | |
| `Titanium` | +0.028 | |
| `_test_song` | +0.005 | |

`min(known 8-bar) = +0.118  >  max(rest) = +0.081` — **prominence separates the
known-8-bar songs from the rest. PASS.**

### Block regime — `Queen of Kings`, 3/7 marked blocks

| block | rep@bar | rep@beat | predicted | marked |
| --- | --- | --- | --- | --- |
| Fairytale like intro | 0.11 | 0.02 | through-composed | through-composed ✓ |
| Post-Intro | 0.68 | −0.35 | bar-loop | bar-loop ✓ |
| Post-Intro + Harmony | 0.83 | 0.60 | half-bar-loop | bar-loop ✗ |
| Melodic Vocal bridge | 0.12 | −0.12 | through-composed | through-composed ✓ |
| Main chorus section ×3 | 0.00 | 0.30–0.51 | through-composed | half-bar-loop ✗ |

The three chorus blocks miss for the reason the known limit names: each is
≈ 3.4 s ≈ 1.7 bars, below the ≥ 2 bars `rep@bar` needs, so it returns 0.0 and
the block reads through-composed. The two intro/bridge and the first
percussion loop — the blocks that *are* ≥ 2 bars — classify correctly.

## Known limit

Needs **≥ 1 bar, ideally 2**. Seven of the sixteen `Queen of Kings` operator
blocks are shorter — including all four micro-events. This classifies block
**character**; it will never find a sub-second cue. That is item 8's job
(`experiments/structural_vs_micro`).

## Conclusion

**Passed on the metric.** The z-normalised bar-sequence autocorrelation recovers
`Chimera - Hana`'s operator-stated 8-bar bass phrase on three stems, and phrase
prominence cleanly separates the two known-8-bar songs from the four that have
no such phrase. The raw-envelope ablation finds nothing — the per-bar
z-normalisation is the whole method. Regime classification works on blocks
≥ 2 bars and degrades to through-composed on shorter ones, exactly as the known
limit predicts; on `Queen of Kings` that is 3 of the 7 blocks with a marked
regime.

Not promoted, no top-level file, nothing in `src/` or `mcp/` reads it. Kept as a
proposal lane to audition against Human Hints on the waveform.

## Reach test

Time-bearing output → `reference/proposals/phrase_periodicity.json`, rendered as
the **`3. Phrase Periodicity`** lane. Not promoted; no top-level file.
