# Experiment — Section Names

*(no external model or repo — classical, numpy; reads `phrases.json` as data and calls `gestures.py`'s snare-roll / riser / reverse-cymbal detectors as functions)*

## Status

**Built and run 2026-10-01 (v3.10 item 17): 191 named blocks over 27 songs
(26 named, 1 kept on its current labels; 38 build→drop units).** Against the
operator-reviewed labels of the 10 reviewed songs the stage names are more
accurate than allin1's mapped labels (exact 0.391 vs 0.316, peak-vs-not 0.716
vs 0.677) and find far fewer boundaries (F1 0.330 vs 0.633). *Rapture* names
both drops `Drop`. **Neither *Armin - Revolution* nor *Medicine-MilkInc* shows
the full stage sequence** (6/10 and 7/10 stages in order; details below).
Nothing in `src/` reads anything here. Queue row enabled. Debugger lane
**Section Names** (flask badge). Promotion waits on the operator's lane review.

## Why? What for?

A moving-head show is authored per stage: the build ramps, the Pre-Drop
blacks out, the Drop fires. `sections.json` carries allin1's Harmonix labels
(`verse`/`chorus`/`inst` mapped to the vocabulary), which say nothing about
that. `docs/segments-vocabulary.md` has the stages and the typical EDM
sequence; the operator's reviewed segments use them.

Question:

> Given the phrases (item 15), do the song's build→drop units — a kick or bass
> ENTRY together with a HIT — plus a section's position in the typical
> sequence name the sections better than allin1's mapped labels, without
> moving the boundaries the operator already reviewed?

Incumbent: allin1 raw segments with the production label mapping
(`analyzer.section_vocabulary.HARMONIX_TO_VOCABULARY`). Baseline: one constant
label (the reviewed corpus's most common, `Chorus`). Reviewed
`reference/human/segments.json` is the **scoring reference, never an input**.

## Method

Inputs (all data; `paths.py` lists them): `reference/proposals/phrases.json`
(required), `loudness.json`, `beats.json` (times and `off_grid_spans` only —
never a bar or downbeat), `arrangement_state.json` (`vocals_phrase`),
`song_event_timeline.json` (`impact` rows only), the drums and mix FFT bands,
`gestures.py` primitives, the structure hint (prior only), and `sections.json`
(`start`/`end`/`function`/`function_confidence`, only to keep them when a song
has no unit). `energy` / `tension` and every other `sections.json` field are
never read.

1. **Per-beat series** (`features.py`): kick = drums-stem FFT below ~150 Hz
   (never `drum_events`), bass and vocals loudness; "on" = the same fractions
   of the song's own p95 that `phrases` uses (kick `max(0.2, 0.5 p95)`, bass
   `0.35 p95`). **Near-silence**: mix level <= 0.12 of the song's mix p95 and
   every stem <= 0.20 of it, runs >= 0.25 s, merged within 0.12 s.
2. **Drops first** (`label.find_runs`). A phrase start `S` is a drop when
   `0.5 x entry + 0.5 x hit`, times `0.7 + 0.3 x phrase confidence`, reaches
   **0.45** and both are non-zero. *Entry*: kick or bass presence over the 8
   beats after `S` >= 0.6 and at least 0.5 above the 8 beats before (silent
   beats ignored), scaled 0..1. *Hit*: a gestures `impact` within 2 beats of
   `S` (its confidence), or a near-silent gap ending within -2/+1 beats of
   `S` (0.8). **Never drum density** (a half-time drop has fewer hits). `S`
   needs 8 beats of song before it; a drop before 20 s needs +0.15 unless the
   hint says radio edit; a phrase that repeats a phrase of an earlier drop
   needs 0.15 less. The run continues while the phrase's kick or bass
   presence is >= 0.5. A groove-off phrase of <= 32 beats where the groove
   returns **to a phrase of the same drop** (`repeat_of`) is a `Drop Break`.
   A run shorter than 8 beats is not a drop.
3. **Names by position** (`label.label_song`), per unit:
   * the drop run is `Drop`, or `Chorus` when its first phrase is sung
     (vocals presence >= 0.5), unless the hint says the chorus is not the drop;
     a run that repeats an earlier run's first phrase **inherits** that run's
     label. The run's last phrase is `Post-Chorus` when short (<= 16 beats),
     bass on, kick off.
   * before the hit: near-silence across all stems ending at the hit =
     **`Pre-Drop`** (<= 8 beats); a snare roll / riser / reverse cymbal /
     vocal-phrase pickup ending where the gap starts (or at the hit if there
     is none) = **`Fill`** (<= 8 beats). Both = two sections, Fill then
     Pre-Drop. Their starts sit on their own physical time (snapped to a
     trusted beat within 1 beat), not on a phrase edge: they are shorter than
     any phrase.
   * **`Build-Up`**: the consecutive phrases before the carve-outs with build
     evidence (snare-roll density >= 0.15, riser >= 0.05, an opening filter
     sweep, a noise sweep, kick drop-out near the end, ends on a gap), capped
     at 64 beats (16 bars of 4/4). The stretch's first phrase (the Intro, or
     the phrase after a drop) is never wholly Build-Up: a build reaching into
     it starts where its own roll / riser / opening sweep starts.
   * `Pre-Build`: the phrase before the Build-Up when an earlier phrase exists
     and it is <= 48 beats and not build-like. First phrase of the song and
     other pre-build phrases without a full groove: `Intro`; kick and bass both
     on: `Main`; the first groove-off phrase after a drop: `Breakdown`.
   * after the last drop: `Outro`, at most 128 beats (32 bars) from the end;
     earlier trailing phrases are `Breakdown` / `Main`. A run that reaches the
     end ends in `Outro` when its last phrase is <= 24 beats with bass out.
   * a **Fill can close any phrase**: a roll / riser >= 2 beats ending within
     a beat of the end of a phrase >= 12 beats long becomes a `Fill` of at
     most 4 beats.
4. **Boundaries** are phrase edges, except a Fill / Pre-Drop start and a
   Build-Up start that reaches into a long phrase (their own evidence time).
   Each block says which: `start_kind` = `song_start`, `phrase_edge`,
   `evidence` (snapped to a trusted beat) or `evidence_unsnapped` (no trusted
   beat within a beat: left at the physical time, never forced). Adjacent
   blocks with the same label and unit merge. Every block has a `confidence`
   (a heuristic score from the drop's entry/hit score and the phrase
   confidence, times a per-label factor — **not calibrated**).
5. **The hint is a prior only** (`prior_from_hint`; no hint = the same run
   with defaults): subgenre `trance`/`big_room`/`dubstep`/`drum_and_bass` ->
   acceptance -0.05; `house`/`techno` (or `shape.drops == 0`) -> +0.15 and an
   empty result is reported as expected; `big_room` or `shape.drops >= 2` ->
   a second wave is searched at -0.15 when only one is found; `trance` ->
   build cap 128 beats; `radio_edit` -> no early-drop penalty;
   `shape.chorus_is_drop == false` -> a sung run stays `Drop`.
6. **No unit** -> `status: "kept_current"`, the current `sections.json` rows
   returned with `source: "sections.json"`, the label's own
   `function_confidence` (or null), and a `status_reason`.

Output `reference/proposals/section_names.json`: `status`, `status_reason`,
`units[]` (`kind` `build_drop`/`drop_only`, `entry`, `hit`, `hit_kind`,
`confidence`, `build_start_s`, `pre_drop`, `fill`, `inherited_from`),
`blocks[]` (`id`, `start_s`, `end_s`, `label`, `confidence`, `why[]`, `unit`,
`phrase_ids`, `start_kind`, `inherited_from`, `source`), and the hint prior
used in `generated_from.hint`.

## Run

```bash
docker compose run --rm --no-deps app python -m experiments.section_names.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.section_names.run export  --all-songs
docker compose run --rm --no-deps app python -m experiments.section_names.run score    # out/score.txt, out/overrides.txt
docker compose run --rm test python -m pytest experiments/section_names/tests -q
```

`compute` caches `cache/<song>.json`; `phrases` must be exported first (the
queue order does it). Exports are byte-identical on a re-run.

## UI lane

**Section Names** (`sectionNames`, flask badge, after Phrases). Label = the
stage name (`Name · confidence` when wide); rows kept from `sections.json` are
tinted grey and say so; the inspector lists the evidence (`why`), the phrase
ids, whether the start is a phrase edge or its own evidence time, and the
inherited label.

## Scoring

`score.py`, the 10 songs with `reference/human/segments.json`. Label
accuracy = share of the reviewed time (0.1 s grid) where the label equals the
reviewed one; **exact**, **coarse** (Build = Build-Up, Break = Breakdown,
Chorus (Inst) = Chorus, Extended Drop = Drop), **peak** (Drop / Chorus /
Post-Chorus / Chorus (Inst) / Drop Break vs. everything else: did it find the
payoff, whatever it is called). Boundary P / R / F1 at +-1.0 s
(`truth_common.structure`). Methods: section_names with the hint (what is
exported), without it, allin1 mapped, majority label. Songs kept on their
current labels would not be scored; none of the 10 reviewed songs is.
`out/overrides.txt` lists every reviewed label and boundary the proposal
would override.

## Results

Pooled over the 10 reviewed songs:

| | section_names (hint) | no hint | allin1 mapped (incumbent) | majority (`Chorus`) |
| --- | --- | --- | --- | --- |
| label accuracy, exact | 0.391 | **0.406** | 0.316 | 0.189 |
| label accuracy, coarse | 0.409 | **0.423** | 0.331 | 0.221 |
| label accuracy, peak vs not | **0.716** | **0.716** | 0.677 | 0.416 |
| boundary P / R / F1 @ 1 s | 0.547 / 0.236 / 0.330 | 0.537 / 0.236 / 0.328 | 0.714 / 0.569 / **0.633** | — |

Per song, exact accuracy (boundary F1): *Charli-VonDutch* 0.901 (0.667),
*Rapture* 0.692 (0.625), *Sash* 0.372 (0.125; 0.515 without the hint),
*Yonaka* 0.329 (0.353), *ayuni* 0.356 (0.400), *Cinderella* 0.340 (0.182),
*_test_song* 0.238 (0.400), *Queen of Kings* 0.249 (0.191), *What a Feeling*
0.234 (0.118), *Armin* 0.116 (0.364). allin1 is better on 6 of 10 songs;
section_names is better on *Charli*, *Rapture*, *Sash*, *ayuni*, *_test_song*
by large margins and loses by large margins on *What a Feeling*, *Armin*.

Required songs:

* ***Rapture* names both drops `Drop`** (55.4 s, 169.8 s; the second inherits
  the first's label from its `repeat_of`). It also names the 125.6 s
  sung run `Chorus` (reviewed `Chorus`), and the intro / pre-build / build /
  breakdown / outro stages. It calls the reviewed 9-s and 15-s `Pre-Drop`
  stretches `Build-Up` and finds no Fill / Pre-Drop before either drop (no
  near-silence there), and adds a `Build-Up` in the second half of the
  reviewed `Breakdown`.
* ***Armin - Revolution* does NOT show the full sequence**: `Intro > Build-Up >
  Chorus > Build-Up > Chorus > Breakdown > Fill > Chorus > Breakdown > Chorus`,
  6 of 10 stages in order (no Pre-Build, one Build-Up, no Pre-Drop, no Outro).
  The audio gives no basis for the reviewed Drop at 59.6 s: kick and bass
  presence are ~0 and the mix is quieter than the build (drums stem 0.00 for 40
  beats), so the units it finds are later vocal-led kick entries named
  `Chorus`. Exact accuracy 0.116: above the majority label (0.072), below allin1 (0.239).
* ***Medicine-MilkInc* does NOT show the full sequence either** (it has no
  reviewed segments, so only the order is checkable): `Intro > Build-Up > Fill
  > Drop > Fill > Breakdown > Build-Up > Drop`, 7 of 10 stages in order: no
  Pre-Build, no Fill/Pre-Drop before the second drop and no Outro (the song
  ends inside the drop). Its 90-s phrase 3 makes a 106-s `Intro` and the first
  drop is only found at 113 s.

Reviewed labels and boundaries it would override (`out/overrides.txt`): of 133
reviewed sections, **98 get a different dominant label**; of 123 reviewed
boundaries, 19 are moved by 1–4 s, **75 have no proposal boundary within 4 s**,
and the proposal adds 23 boundaries with no reviewed counterpart. The cause is
structural: a drop run lasts as long as kick or bass stays on, so *Cinderella*
(1 Drop of 130 s), *Sash* (136 s) and *Queen of Kings* (98 s) swallow the
reviewed Verse / Main / Refrain / Breakdown / Chorus sections inside them, and
phrase edges are coarser than reviewed sections. Promotion would remove the
human tier from `sections.json` on exactly these songs; the reviewed file stays
the rollback.

Corpus: 191 blocks — Intro 33, Build-Up 28, Drop 26, Chorus 22, Outro 19, Fill
18, Main 18, Breakdown 14, Pre-Build 8, Verse 3 (kept labels), Pre-Drop 1,
Drop Break 1. Starts: 26 song start, 120 phrase edges, 33 evidence times, 12
kept. **`Pre-Drop` fires once** (*Charli-VonDutch*): near-silence across all
stems before a hit is rare in this corpus, and the reviewed Pre-Drops (3 on
*Rapture*, *Armin*, *Cinderella*) are stretches of reduced music, not silence.
Kept on current labels: *Pet Shop Boys - I'm not scared* (no entry + hit);
no house/techno song is in that state because their drops pass the +0.15 bar
anyway. The hint changed the output of only 2 of 27 songs (*Armin*, *Sash*,
both trance, through the doubled build cap): it did not help.

## Tuning disclosure

Every constant is a priori from the vocabulary doc and was never swept. The
rules, however, **were corrected after reading the reviewed songs' output**
(*Rapture*, *Charli-VonDutch*, *Medicine-MilkInc*, *Sash* first), so the
figures above are optimistic and *Rapture* / *Charli* in particular are the songs
the rules were fixed on:

| change after the first run | why | pooled exact accuracy / boundary F1 |
| --- | --- | --- |
| (first run) | — | 0.256 / 0.321 |
| a drop needs a hit as well as an entry | a lone bass entry at *Rapture* 33 s was a "drop" | 0.417 / 0.353 |
| a Drop Break must return to a phrase of the same drop; a drop needs 8 beats of song before it | *Charli*'s breakdown was a Drop Break; *Medicine* "dropped" at 1.75 s | (same step) |
| the stretch's first phrase is never wholly Build-Up; opening sweeps count as build starts | *Rapture*'s breakdown was a Build-Up (and *Charli*'s intro) | 0.374 / 0.322 |
| Outro capped at 128 beats | *What a Feeling* was 130 s of Outro | 0.391 / 0.330 |

Two later changes were bug fixes with no effect on the reviewed scores (the leading
part of a long Build-Up phrase took the `Pre-Build` label; `Pre-Build` now needs
the Build-Up to start on a phrase edge). The step that lowered accuracy was kept because it is musically right (an
Intro or a Breakdown is not a Build-Up) and the pooled drop is within noise of
10 songs. The first row's figure also had the early-drop penalty and the
8-beat lead already in. Not tuned: the 0.45 acceptance, the 0.6 / 0.5 entry
thresholds, the silence fractions, the 64 / 128-beat caps, the confidence
factors.

## Known weaknesses

* **Phrases are the ceiling.** A reviewed section inside one phrase (a
  mid-phrase breakdown, a 20-s verse inside a drop) cannot be named; *Medicine*
  phrase 3 is 90 s. Only Fill / Pre-Drop / Build-Up starts may leave the phrase
  edges.
* **A drop run lasts as long as kick or bass stays on**, so songs whose
  groove never stops after the first drop get one very long `Drop` / `Chorus`.
* Songs whose reviewed drop has no kick/bass entry (*Armin*) are named from the
  wrong evidence; the entry + hit rule has no answer for them.
* `Pre-Build`, `Verse`, `Bridge`, `Refrain`, `Mid-Intro`, `Extended Drop` are
  never produced (`Verse` only as a kept label); `Chorus` vs. `Drop` is decided
  by vocals presence alone.
* Confidence is a heuristic score; it is not calibrated and the pooled data
  cannot calibrate it.
* Hints: only `trance` is in the reviewed set; the `big_room` second-wave and
  `house`/`techno` paths are unit-tested but have no reviewed song to score.

## Reach test

Time-bearing output -> `reference/proposals/section_names.json`, the **Section
Names** debugger lane. On promotion the published `sections.json` `function`
and boundaries would take these names on every song (the human tier included —
`reference/human/segments.json` itself stays the scoring reference and the
rollback). Not promoted; no top-level file.
