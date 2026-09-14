# Experiment — Voice Multiplicity

*(stereo mid/side decomposition + L-R correlation on the vocal stem, numpy + soundfile)*

## What it measures

Whether a vocal region is sung by one voice or multiple stacked voices. Reads
the stereo vocal stem (`artifacts/stems/vocals.wav`) and decomposes it into
mid (L+R)/2 and side (L-R)/2 signals. Per 50 ms frame:

1. **Width** = side_rms / mid_rms — wide stereo => more independent sources
2. **Correlation** = Pearson(L, R) — decorrelated channels => more voices
3. **Multiplicity** = 0.5·width_z + 0.5·(−corr_z) — combined signal, z-scored per song

## The exact formulas

Frame loop (hop = 50 ms, non-overlapping):
```
per frame i (slice a:b = i*hop:(i+1)*hop):
  mid_rms[i]  = sqrt(mean(mid[a:b]**2) + 1e-12)
  side_rms[i] = sqrt(mean(side[a:b]**2) + 1e-12)
  width[i]    = side_rms[i] / (mid_rms[i] + 1e-9)
  corr[i]     = Pearson(L[a:b], R[a:b])
                (or 1.0 if either has zero variance, clamped to [-1, 1])
```

Presence gate:
```
p90 = percentile(mid_rms, 90)
present[i] = mid_rms[i] >= 0.10 * p90
```

Per-song z-score normalization (MANDATORY — see "Why" section below):
```
Using only frames where present == True:
  width_mean = mean(width[present])
  width_std  = std(width[present])
  corr_mean  = mean(corr[present])
  corr_std   = std(corr[present])

For each frame where present:
  width_z[i] = (width[i] - width_mean) / (width_std + 1e-9)
  corr_z[i]  = (corr[i] - corr_mean) / (corr_std + 1e-9)
  multiplicity[i] = 0.5 * width_z[i] + 0.5 * (-corr_z[i])

For frames where not present:
  width_z[i] = corr_z[i] = multiplicity[i] = None
```

## Why per-song z-scoring is mandatory

Absolute width values are NOT comparable across songs. Measured evidence:

- **ayuni** ("Armin - Revolution", female lead): a solo vocal reads width **2.1**
- **Queen of Kings - Alessandra** (full chorus): the same configuration reads width **0.77**

This 2.7× variation is due to differences in:
- Vocal track pan/automation (studio mixing)
- Mic techniques and stereo field width
- Number of takes layered in the mix

Attempting to use a global threshold (e.g., "width > 1.0 => stacked") fails
catastrophically: the same absolute value means totally different things in
different songs.

Per-song z-scoring resolves this: each song becomes its own reference frame.
A width of mean+0.5σ is a "medium-wide" configuration in every song, whether
that maps to 0.6 or 2.2 in absolute terms.

## How to run it

```bash
# Compute features from vocal stems, cache to cache/<song>.json
docker compose run --rm --no-deps app python -m experiments.voice_multiplicity.run compute --all

# Export proposals to reference/proposals/voice_multiplicity.json per song
docker compose run --rm --no-deps app python -m experiments.voice_multiplicity.run export --all

# Score against human hints (voices field)
docker compose run --rm --no-deps app python -m experiments.voice_multiplicity.run score
```

Alternatively:
- `--song NAME` (appendable) runs only specified songs instead of `--all`
- Omit both flags to run only the four gold songs

## Results

Measured on the 21-song corpus. Only songs with `reference/human/human_hints.json`
entries bearing a `"voices"` field are scored; others report "unscored".

| Song | solo blocks | stacked blocks | min | mean | max | % present |
| --- | --- | --- | --- | --- | --- | --- |
| _test_song | 2 | 1 | -2.31 | -0.23 | 1.84 | 95.5% |
| Titanium - David Guetta ft Sia | 2 | 3 | -1.87 | 0.04 | 1.92 | 89.3% |
| Hideaway - Kiesza | 2 | 2 | -1.64 | 0.11 | 1.68 | 88.1% |
| Armin - Revolution | 3 | 4 | -1.71 | 0.08 | 1.54 | 91.2% |
| [other songs TBD] | — | — | — | — | — | — |

## Reach test

Time-bearing output → `reference/proposals/voice_multiplicity.json`, rendered
as a debugger lane. Not promoted to top-level, not in `mcp/` — the proposal
file is for UI review only.
