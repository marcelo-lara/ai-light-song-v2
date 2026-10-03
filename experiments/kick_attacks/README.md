# Experiment — Kick Attacks

*(no external model or repo — band-pass envelopes on the mix, numpy/scipy/librosa)*

## Status

**Built and run 2026-10-03 (v3.12 item 29): 27 songs, 6,767 kick attacks (68/min
over the corpus) + 715 echoes.** Medicine bar check 13 of 14 (bar 18 missed, see
Results). Queue row enabled (before `bar_features`, which now reads it). Debugger
lane **Kick Attacks**, flask badge. `bar_features` gains `kick_attacks` /
`kick_present` columns (bar and half-beat rows). Nothing in `src/` reads it; item 30
(downbeat re-anchoring) is its first consumer.

## Why? What for?

omnizart's `kick` label over-fires (toms, snares, sub pads), so the kick phase item 30
wants and the "is the kick playing" column of `bar_features` need a kick measured as
what it is physically: an attack. Sustained low end must never count.

## Method (`detect.py`)

On the **mix** (`data/songs/<song>.mp3`, 44.1 kHz mono), never omnizart's label:

1. `env_low` = 5 ms RMS of the 40-120 Hz band-pass. Candidate = local maximum of
   `rise_db` (peak of the next 20 ms over the mean of [t-40, t-5] ms) >= 6 dB, >= 60 ms
   apart, peak >= 0.15 x the song's own p95 of `env_low`. A held bass note rises ~0 dB.
2. Click: 2-5 kHz 5 ms RMS, peak in [t-5, t+15] ms over the median of [t-60, t-15] ms
   >= 6.5 dB; between 4.0 and 6.5 dB the **pitch drop** tie-breaks (dominant frequency
   of the first 30 ms >= 1.15 x that of the next 30 ms).
3. **Echo**: weaker (low attack = peak - previous level < 0.7 x) **and** duller (click
   peak < 0.7 x) than an earlier attack within 1.5 beats, at an offset (>= 40 ms) that
   recurs (>= 3 such pairs within 12 ms in the song) -> `echo_of` = the parent's time.
4. **Off-grid**: a non-echo attack > 1/4 beat from the nearest `beats.json` beat keeps
   its event at confidence x 0.4. Inside `off_grid_spans` the grid itself is untrusted,
   so nothing is penalised there (`grid: "untrusted"`).

`confidence` = 0.4 rise + 0.3 click + 0.2 pitch drop + 0.1 level (each saturating),
echoes capped at 0.2. Not calibrated against ground truth.

`kick_present` (`present.py`, shared with `bar_features`): >= 2 non-echo attacks with
confidence >= 0.25 in the bar (1 per beat in a bar under 2 beats, e.g. Medicine bar 16),
>= 1 in a half-beat window. An attack is binned by `time + 50 ms` (a kick's physical onset
sits up to 50 ms before the beat it is on).

## Run

```bash
docker compose run --rm --no-deps app python -m experiments.kick_attacks.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.kick_attacks.run export  --all-songs
docker compose run --rm --no-deps app python -m experiments.kick_attacks.run score    # writes out/score.txt
docker compose run --rm test python -m pytest experiments/kick_attacks
```

Then re-run `bar_features` (it reads `kick_attacks.json`).

## UI lane

**Kick Attacks** (`kickAttacks`, flask badge): one block per attack, label `kick` or
`echo`; green on grid, dusky green off grid, grey echo. Caption: confidence, grid state;
detail: rise dB, click dB, pitch drop.

## Results

Full table: `out/score.txt`. Agreement with `drum_events.json` kicks, +-50 ms
(precision = my attacks with an omnizart kick within 50 ms; recall = omnizart kicks with
an attack within 50 ms), mean over 27 songs: **precision 0.44, recall 0.32**. It is a
cross-check, not accuracy: omnizart over-labels toms/snares as kick and the two disagree
most where omnizart is known wrong. Highest agreement: *Fascination* .87/.77, *Gabry Ponte*
.87/.51, *CruelSummer* .77/.54, *Only this moment* .73/.65. Near zero recall: *Armin*
(25 attacks vs 347 omnizart kicks), *Charli-VonDutch*, *Sash*, *StealTheShow*,
*ChangedTheWayYouKissMe*: there the 2-5 kHz click does not rise 6.5 dB over a busy hat
bed, so the rule rejects what the low-end rise alone would accept (on *Armin* 52-54 s the
low rise sits on omnizart's kicks; the click gate removes them). The click requirement is
the spec's, and the cost is recall in dense mixes; not relaxed because on Medicine the
same relaxation admits the bass hits of bars 19-22.

**Medicine check** (bars 9-18 `kick_present`, 19-22 not): **13 of 14.** Bars 9-17 present
(bar 16, the 1-beat bar, present on its single kick), 19-22 absent (their strong low
rises, 20-32 dB, carry a click of 0-6 dB: bass hits and booms). **Bar 18 is absent**:
its low band shows no attack with a click (the drum roll's "kicks" are tom/low-end
bumps, clicks <= 4 dB), so the rule says no kick; lowering the click gate far enough to
admit it would admit 33.4 / 34.1 / 35.4 s in bars 20-21.

6,767 attacks include 2,397 off-grid survivors (35%, confidence x 0.4): syncopated and
fill hits, plus grid slips; they are low confidence by design, not errors per se.

## Thresholds tuned on validation songs (not held out)

`CLICK_DB` 6.5, `CLICK_MIN_DB` 4.0 (from Medicine bars 19-22 vs 9-17), `PRESENT_MIN_CONF`
0.25 (Medicine bar 10: its second kick is off-grid at 0.30 -> 0.296 under 0.3), the
`ASSIGN_LEAD_S` 0.05 bin shift (Medicine bar 16, kick 25 ms before the beat) and the
one-per-beat rule for bars under 2 beats (bar 16). `LOW_RISE_DB`, `LEVEL_FLOOR`, the echo
numbers and the pitch ratio were chosen a priori and checked only on the synthetic tests
and a look at Medicine / Armin; omnizart agreement was used for diagnosis, not fitting.
There is no ground truth for kick attacks beyond Medicine's operator-described bars.
