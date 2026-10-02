# Product refinement — v3.10

**Status: partly implemented.** Items 3, 5, 6, 7, 8, 9 and the empty-reviewed-segments
bug are done. Items 2, 4, 10 and 11 are built as experiments (plan items 14-17)
and stay open until the operator's lane review gives a promotion verdict, in
build order 11 → 2 → 10 → 4. Item 1 and the crash bug moved to
[`product-backlog.md`](product-backlog.md).

---

## 11. Filter sweeps — experiment first

*Built as experiment (item 14 of the plan), awaiting lane review verdict.*

**Change.** A new primitive, `filter_sweep`, built as an experiment with its
own lane and promoted into `gestures` on the operator's verdict: brightness (spectral
centroid from the published per-stem FFT bands) moving near-monotonically
over 2–16 bars on the harmonic and bass stems while their loudness stays
roughly level. Fields: `direction` (`opening` | `closing`), `stem`, span,
`depth` (centroid change), confidence.

Distinct from `riser`, which is high-band energy rising (a new sound getting
louder); a sweep is the existing music changing tone. Computes its own
centroid: `energy.py`'s was cut in v3.10.

| | |
| --- | --- |
| Writes | `reference/proposals/filter_sweep.json` (experiment); `song_event_timeline.json` `filter_sweep` rows only on promotion |
| Reads changed | new `experiments/filter_sweep/`, `queue.toml` row, lane "Filter Sweeps"; on promotion `gestures.py`, `docs/mcp-definition.md`, `downstream-contract.md` |
| Done when | a sweep is reported on a song where one is heard (operator names it in the lane review), and none on steady sections of the same song |

---

## 2. Phrases from audio changes — experiment first

*Built as experiment (item 15 of the plan), awaiting lane review verdict.*

**Change.** A phase-3 phrase layer cuts the song where the audio changes:
`arrangement_state` stem entries/exits plus `gestures.py` impacts, pre-drop
gaps and riser/snare-roll ends, each edge at the beat nearest to it. Each phrase
carries kick/bass/vocal presence, riser and snare-roll density, item 11's
filter sweeps, white-noise sweep (rising noise in the published FFT bands),
whether the kick drops out near its end (kick presence = drums-stem energy
below ~150 Hz, never `drum_events`' kick, which folds in toms and ghost hits), whether it ends on a gap, the earlier phrase it repeats, and a confidence. Disagreeing
evidence publishes the phrase `resolved: false`, never a forced edge.

No bar counting: the phrase grid is never derived from downbeats or a fixed
bar length (downbeat F1 0.234; `grid_consensus`'s 8-bar grid scored 0/7, and
radio edits break any count). `stem_presence_sections` is folded in as an
input, not promoted on its own.

| | |
| --- | --- |
| Writes | `reference/proposals/phrases.json` (experiment); a top-level file only on promotion |
| Reads changed | new `experiments/phrases/`, `queue.toml` row, lane "Phrases" |
| Done when | boundary precision/recall against the reviewed segments and hints, EDM-shaped songs reported apart from the rest; *Rapture* and *Charli-VonDutch* match their stem-presence results or better |

---

## 10. Downbeats anchored on phrase edges — experiment first

*Built as experiment (item 16 of the plan), awaiting lane review verdict.*

**Change.** Every confident item-2 phrase edge on a stem entry or impact is a
downbeat. Between two anchors, bars are counted in fours on the trusted beat
times; anchors that disagree on the phase mark the span between them
`resolved: false`. allin1's phase stays only where no anchor reaches. This
is local phase from audio changes, not a song-wide grid or a phrase count.
Built as an experiment reading item 2's proposals (`src/` never imports
`experiments/`); `timing.py` changes only once items 2 and 10 are promoted.

| | |
| --- | --- |
| Writes | `reference/proposals/downbeat_anchors.json` (experiment); `beats.json` `type`/`bar`/`beat`/`downbeat_confidence` only on promotion |
| Reads changed | new `experiments/downbeat_anchors/`; on promotion `timing.py` or a phase-3 re-phasing stage |
| Done when | downbeat F1 against the Moises downbeats beats today's 0.234 (`analysis-definition.md`, "Downbeats") |

---

## 4. Stage names and section normalization — `sections.json`

*Built as experiment (item 17 of the plan), awaiting lane review verdict.*

**Change.** Every section, on every song including reviewed ones, is
renamed using the stage terms of
[`segments-vocabulary.md`](segments-vocabulary.md) and its boundaries snapped
to item 2's phrase edges. A section's position in the vocabulary's typical
EDM sequence decides its label. The audio only decides where it starts and
ends.

- Build→drop units are found first, then everything around them takes its
  label from where it sits (between Main and Build-Up → Pre-Build; kick out
  after a drop → Breakdown; after the last drop → Outro).
- A Fill (up to 4 beats of drum fill, vocal pickup or riser tail) can close
  any phrase, not only the one before a drop.
- Between build and drop: a near-silent gap across all stems is `Pre-Drop`
  (the show blacks out or freezes); a roll, vocal or riser is `Fill`. Both in
  a row → two sections.
- A phrase that repeats an earlier one inherits its label (drop 2 from
  drop 1).
- A drop is found from the kick/bass entry plus the hit, never from rising
  drum density: a half-time (dubstep) drop has fewer hits, not more. A drop
  with no build before it is found the same way.
- The kick dropping out near a build's end marks where the build ends and
  the Fill/Pre-Drop starts.
- In a radio edit, a drop or sung chorus in the first minute is normal; the
  intro may be short or missing.
- Every label carries a confidence. A song with no build→drop unit keeps its
  current labels, attributed as such; for house/techno this is the expected
  result, not a failure.

Operator reviewed segments and hints are the scoring reference, never inputs.
On promotion the normalized labels and boundaries replace the human tier in
`sections.json` on every song; `reference/human/segments.json` itself is
never edited, so it stays the scoring reference and the rollback. Every
reviewed boundary or label it overrides is listed in the experiment's
report. `energy` and `tension` are ignored. Nothing reads external apps.

| | |
| --- | --- |
| Writes | `reference/proposals/section_names.json` (experiment); `sections.json` `function` and boundaries only on promotion |
| Reads changed | new `experiments/section_names/`, lane "Section Names" |
| Done when | label accuracy and boundary moves on the reviewed songs reported against allin1's mapped labels; *Rapture* names both drops `Drop`; *Armin - Revolution* and *Medicine-MilkInc* publish the full stage sequence |
