# Findings — `Queen of Kings - Alessandra`, first 64 s

Source: operator hand-analysis of the first minute
(`reference/human/human_hints.json`, 16 hints) plus Moises word-level lyric
timings (`reference/moises/lyrics.json`, first 34 bars fine-tuned), compared
against the published auto inference.

Song facts: 125.98 BPM, 4/4 ⇒ 1.905 s/bar. Duration 146.4 s.

## 1. allin1's function labels are anti-correlated with energy

Per-stem mean RMS from `loudness.json`:

| passage | allin1 label | mix | drums | what it actually is |
| --- | --- | --- | --- | --- |
| 3–15 s | **chorus** | 0.12 | **0.007** | softest, drumless "fairytale intro" |
| 17–30 s | verse | 0.13 | 0.14 | tribal percussion enters |
| 32–45 s | chorus | 0.13 | 0.016 | melodic bridge + build, still no drums |
| 49–60 s | *(mid-chorus, no boundary)* | **0.17** | **0.20** | the drop |
| 64–78 s | verse | 0.17 | **0.23** | the "intense verse" |

"chorus" sits on the two quietest passages; "verse" sits on the two loudest.
Eurovision-shaped song — the post-chorus hook and driving verse out-punch the
sung chorus, and allin1's training prior does not fit it.

**Consequence:** a cue model reading `sections.json` sees `chorus` at 1.1 s and
lights the calmest moment in the song like a climax.

**Fix — phase 3, lands in `sections.json`:** cross-check each allin1 `function`
against `arrangement_state` + `loudness`. When a "chorus" is quieter and thinner
than the "verse" that follows, set `function_status: "contested"` or flip it.
`function_confidence` here is 0.48–0.85 — low enough that the energy
contradiction should win.

## 2. The drop at ~48.7 s reaches no published file as a first-class fact

`gestures.py` locates it correctly — impact conf 1.0, on downbeat, tension gap
at 47.3, release 48.7–52.5 — and `reference/proposals/drop_impacts.json` agrees
(47.76 / 48.7). Two defects stop it reaching the authoring model:

- `sections.json` has **no boundary** there. It sits 17 s inside allin1's 32 s
  `section-004` "chorus" (31.42–63.49). Split into build (31.4–48.7) +
  chorus (48.7–63.5).
- In `song_event_timeline.json` it is 1 of 31 impacts and **every impact carries
  `intensity: 1.0`**. The drop and an off-beat kick at 57.1 s are
  indistinguishable.

**Fix:** grade impact intensity by combined evidence (transient magnitude ×
sub-band energy × on/off-downbeat × preceding build × following release ×
section alignment), and add a song-level **primary-climax** marker. The 48.7
event has every one of those; 57.1 has none.

## 3. Vocal phrasing is the dominant signal here and is not published at all

12 of the 16 human hints are vocal-driven ("long tonal phrases", "keeps the
note", "close to silence after vocal long note", "vocals pause"). The Moises
timings reproduce that narrative almost exactly:

| lyric evidence | maps to |
| --- | --- |
| "us?" held **3.5 s** (42.98–46.52) | hint-006 "vocal lead keeps the note" |
| gap 46.52–47.23, no words | hint-007 "close to silence" |
| "Her name is she" 47.23–48.66 | hint-008, immediately before the drop |
| gap 52.05–52.39 | hint-010 "micro break" |
| "La-di-da-di-da-di-da" 37.3–39.2 (7 syllables / 1.9 s) | hint-005 the build |

All of it is derivable from the vocals-stem RMS the pipeline already produces,
sharpened by Moises lyrics where present — and it must degrade to stem-only,
since a first run cannot require `reference/`.

**Fix — new top-level file (e.g. `vocal_activity.json`):** phrase spans,
held-note flags (syllable duration > N beats), inter-phrase silence markers with
duration, rough syllable-rate track.

The pattern **long sustained note → silence → impact** is a textbook pre-drop
cue and is highly detectable. `gestures.py` already finds the dropout gap but
never ties it to the vocal sustain that causes it.

## 4. The bar grid is guessed

`beats.json` `downbeat_confidence` is 0.0017 / 0.0109 on the opening downbeats
and `null` thereafter. Yet the structure is metrically regular, and two
independent anchors agree: the 48.7 s drop is called on-downbeat by gestures,
and the operator's "bar 34" ≈ 63.95 s — exactly **8 bars** later at 1.905 s/bar.

**Fix:** use confident impact-on-downbeat events as grid anchors and propagate,
rather than trusting allin1's near-zero downbeat activations. Separately, stop
writing `null` `downbeat_confidence` on non-downbeat rows — carry the phase
confidence to every beat so a reader cannot misread a trusted beat *time* as
low-confidence. (Same defect class as the fused-row confidence problem already
noted for `beats.json`.)

## 5. Smaller detectable cues, none currently surfaced

| cue | evidence in the hints | detection route |
| --- | --- | --- |
| percussion texture change — "tribal" (16.4) vs "drum machine" (63.95) | hints 002, 016 | check whether `drum_events.json` carries enough timbre to emit a "kit changed" event |
| sidechain pumping | hint-013 "rhythmic bass and percussive synth alternates (sidechained)" | sub-band RMS periodicity at the beat rate |
| sub-second micro-events (<0.7 s) — stabs, stutters, the "hey" shout | hints 006, 007, 010, 012 | a "micro-gap / stutter" primitive distinct from the existing pre-drop `tension` span |

Organic-warm vs driving-strobe, and lights breathing with the pump, are real
moving-head distinctions; all three are currently invisible downstream.

## 6. Knock-on — `hints.json` files hints under the wrong containers

Because `sections.json` is wrong, hint-009 "Main chorus section" (the drop)
nests under `section-004 "chorus" 31.42–63.49` alongside 11 other hints. A model
reading that section sees a 32 s "chorus" with 12 crammed hints. Fixing §1–2
resolves this with no separate work.

## 7. What to measure next

The five load-bearing boundaries in the operator's marking, to score the
segmenter against:

| boundary | what changes |
| --- | --- |
| 16.4 s | tribal percussion enters |
| 31.6 s | melodic vocal bridge |
| ~39.2 s | tension build starts |
| **48.7 s** | the drop |
| 63.95 s | verse 2, bar 34 |

Two open questions worth resolving in the same pass: does the 48.7 drop reach
*any* published file, and does the §1 label/energy contradiction reproduce on
the other gold songs or only here.

The impact-ranking work in §2 belongs to the existing open issue *"`gestures` —
per-primitive precision has never been audited"*.
