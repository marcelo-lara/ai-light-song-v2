# Product refinement — v3.9

**Status: implemented** (items 1, 3, 4, 5 and the four listed bugs; item 2 — claps / kick check / crash check — runs as experiments outside the plan).

---

## 1. Vocal cadence from the operator's lyric alignment — new stage, new top-level `vocal_cadence.json`, `mcp/`

**Current behaviour.** `reference/human/lyrics.json` (operator-aligned
token onsets/ends grouped into lines) is read by no stage. Vocals reach the
MCP only as whisperX phrase spans (`arrangement.vocals_phrase`) and a
per-section `rhythm.vocals.onsets_per_beat`, neither of which shows where a
line sits on the bar or against the section's hit.

**Change.** A new stage publishes `vocal_cadence.json` from `lyrics.json` +
`beats.json`. It carries **timing only — never the text.** The operator
aligns lyrics for pace and cadence, not karaoke; the tokens are syllable
groups placed for rhythm, not a word-accurate transcript, so publishing text
would invite the authoring model to light the words. The only text read is the
call marker below.

- **Lines.** Start/end in seconds and bar.beat (both — the downbeat grid is
  partly unresolved on some songs), duration in beats, token count, and
  `pickup: true` when the line starts before the downbeat it resolves on.
- **Per section.** `lead_in_bars`: the downbeat the section's first line
  resolves on (after its pickup), in bars relative to the section boundary —
  0 = the line lands on the hit, −1 = a bar early. Not the raw line-start
  distance, which counts the pickup and so reads a same-shaped entry as
  different amounts. The first line is the earliest one resolving within
  [−2, +1) bars of the boundary and sung continuously (gaps < 1 bar) into the
  section, so a line that starts over a Fill before the drop still counts.
  Rests ≥ 1 beat between
  lines (start, length in beats); held notes (a token ≥ 2 beats); token
  density per bar.
- **Cadence repeats.** For each section, the earlier section whose onset
  pattern it repeats and the **bar offset relative to the two boundaries**
  (onsets matched within 80 ms, plus the match fraction). This is the
  load-bearing field: in *Queen of Kings*, drop 1's line starts on the hit,
  while drop 2 and the final chorus start one bar before theirs (same cadence,
  offset −1 bar). Lighting keyed to the section boundary alone misses that.
- **Calls.** Crowd shouts are distinct events (time, bar.beat), not
  cadence tokens — they are a direct lighting cue. The operator marks them in
  `lyrics.json` as a parenthesised token, e.g. `(hey)`.
- **Tiers.** Human `lyrics.json` > `reference/moises/lyrics.json`;
  `field_sources` names the tier. No lyrics file → `vocal_cadence.json` is
  still written, with `source: null`, empty `lines`/`sections`/`calls` and a
  `reason`, and the MCP says so rather than inferring (the whisperX fields
  already cover the stem-only case). Always writing the file keeps the MCP's
  every-top-level-file-is-required rule; an optional file would be the first
  degraded mode.
- **Phase.** A phase-4 publish stage: `reference/` may feed publishing, never
  an interpret/relate stage. It promotes `experiments/vocal_cadence/` (12/12
  on the done-when facts below); the experiment directory, its queue row and
  its "Vocal Cadence" lane are deleted in the same change.
- **MCP.** `get_detail(section_id=…)` returns the section's block;
  `get_song_overview` rows carry `lead_in_bars`, rest and call counts, and
  the cadence-repeat reference.

Narrative prose stays in `human_hints.json`, only for what timing cannot
express. Supersedes the lyric half of
[`alessandra_findings.md`](alessandra_findings.md) §3.

| | |
| --- | --- |
| Writes | `vocal_cadence.json` (top level, new) |
| Reads changed | new analyzer stage (added to `STAGE_PIPELINE_IDS`), `mcp/` overview + `get_detail` + `REQUIRED_TOP_LEVEL_FILES`, `docs/reference/artifacts.md`, `docs/reference/downstream-contract.md` |
| Done when | on *Queen of Kings*, the MCP reports drop 2 (98.23) as repeating drop 1 at −1 bar, the final chorus (130.63) as repeating drop 2 at 0 bars (and so drop 1 at −1), `lead_in_bars` 0 / −1 / −1 on drop 1 / drop 2 / final chorus, calls at 99.62, 107.21, 131.87 and 139.62 s, and no lyric text anywhere in the response |

---

## 2. Claps as their own accent event — experiment first, then `drum_events.json`

**Current behaviour.** `drum_events.json` (omnizart) labels only
kick/snare/hat/crash, and on a sparse drums stem it reports bleed as hits:
*Queen of Kings*' break (bars 42–48) returns 46 snare/hat events where the
stem holds 7 claps and silence. Nothing tells a clap from a drum-machine hit,
and the operator places accents on claps (hint-019, "Accents live on the
claps, not on the vocal").

**Change.** A `clap` event, detected from the drums stem by its spectrum,
not by omnizart's label. Measured on operator-reviewed hits: claps have a
1–6 kHz noise share of 0.56–0.92 and a 120–400 Hz body of at most 0.12; the
operator-rejected machine hit (*Queen of Kings* 97.29) has 0.10 / 0.28, and
the drops' beat-3 backbeat about 0 / 0.25. The shape must be the test: a
loudness or onset gate alone misses soft claps (it missed bar 47's break clap
and *Tutta L'Italia*'s claps in bars 20–21) and passes machine hits. Runs as a
`docs/experiments.md` entry with a UI lane before any promotion.

**Kick check (sibling experiment).** The same per-hit spectral shape also
tests omnizart's `kick` label, which folds toms and ghost hits in: *Rapture*
publishes 57 kicks/min in the Breakdown (96–125.54) and 37/min in the Chorus
(125.55–155.07), where the operator hears no kick at all; the drops carry
~110–120/min, one per beat at 129.84 BPM. A kick keeps its label only with a
sub/low body and no 1–6 kHz noise share. A separate experiment, because it is
a separate claim with its own error mode and lane; the feature code may be
shared between the two directories.

| | |
| --- | --- |
| Writes | `reference/proposals/clap_events.json`, `reference/proposals/kick_check.json` (experiments); `drum_events.json` gains `clap` / drops failed kicks only on promotion |
| Reads changed | new `experiments/clap_events/` and `experiments/kick_check/`, two `queue.toml` rows, debugger lanes "Clap Events" and "Kick Check" |
| Done when | *Queen of Kings*: all 7 break claps (bar 42–48, beat 3), no clap at 97.29, none on the drop backbeat. *Tutta L'Italia*: claps on beats 2 and 4 in bars 20–25 and in bar 80. *Rapture*: ≤ 5 kicks/min kept in the Breakdown and Chorus, ≥ 100/min in both drops |

---

## 3. Beat-grid honesty where the tracker loses the tempo — `beats.json`, `mcp/`

**Current behaviour.** `beats.json` beat times are called trusted everywhere,
but essentia's tracker loses the tempo where drums are absent. *Rapture*'s
pads-only Pre-Drop (46.15–55.39) has beats ~0.36 s apart (~167 BPM) against
the song's 0.462 s (129.84 BPM); before drop 2 the grid drifts to ~0.485 s,
so the drop's physical hit (169.83) falls between two beats (169.55, 170.05).
A chase locked to that grid runs fast, then late.

**Change.** Fit the song's constant-tempo grid (the corpus is 4/4 at
near-constant BPM) to the beats in stable regions, and publish in
`beats.json` a file-level `off_grid_spans: [{start, end, max_deviation_ms}]`
wherever consecutive beats sit more than a named tolerance (70 ms) off that
grid. Beat times are **not** rewritten: they stay essentia's measurement, and
replacing them with the fitted grid needs its own measurement against the
human impacts first. `get_detail`'s derived `position` reports
`resolved: false` for a time inside a span — the same honesty rule as a
null-confidence downbeat.

| | |
| --- | --- |
| Writes | `beats.json` (`off_grid_spans`, file level) |
| Reads changed | `ui_data.py` (beats publish), `mcp/serializers.py` `_position`, `docs/reference/downstream-contract.md`, CLAUDE.md "trusted" row |
| Done when | *Rapture*: a span covers 46.15–55.39; the beat grid around 169.83 is either within 70 ms of it or inside a span; `get_detail` on the Pre-Drop reports `resolved: false`; the 7/7 human-impact check still passes |

---

## 4. Impacts at the physical onset, and at every drop hit — `song_event_timeline.json`, `sections.json`

**Current behaviour.** `detect_impacts` (`gestures.py`) places an impact at
the peak of the FFT transient, not where the hit starts: *Rapture*'s drop 2
starts at 169.83 (bass and drums stems cross their thresholds in the same
20 ms frame) but the impact reads 170.05 — 220 ms late, so
`impact_alignment` inherits the error. And drop 1's hit (55.39), the loudest
arrival in the song, has no impact at all.

**Change.** An impact's `start` is the onset — the first frame of the rise
that leads to the peak — with the peak kept as `peak_time`. And every
published section boundary where the bass and drums stems both enter within
one beat gets an impact at that stem onset (`evidence` names the stem entry),
if the transient detector did not already produce one there. A cue fired
late is a cue missed.

| | |
| --- | --- |
| Writes | `song_event_timeline.json` (impact `start` meaning, `peak_time`), `sections.json` `impact_alignment` |
| Reads changed | `gestures.py`, `docs/reference/downstream-contract.md`, `docs/analysis-definition.md` gesture numbers |
| Done when | *Rapture*: impacts at 55.39 and 169.83, each within ±40 ms; the gold human-impact score (4/7 @±1.0 s) does not drop |

---

## 5. Split the files every change has to read — `ui/`, `docs/experiments.md`

**Current behaviour.** A few files are read whole on most changes, costing
tokens and context in every session that touches them:

| File | Size | Commits / 3 mo | Shape |
| --- | --- | --- | --- |
| `ui/src/App.tsx` | 1,931 lines, ~20k tokens | 23 | `App()` alone is lines 267–1886: 73 hooks and a ~390-line JSX return |
| `ui/src/timeline/laneContent.ts` | 1,156 lines, ~12k tokens | 18 | 22 independent per-lane `*Content` functions plus the lane registry; every new lane or experiment edits it |
| `ui/vite.config.ts` | 1,166 lines, ~11k tokens | 8 | the dev-server write endpoints (hints, segments, block energy, lyric validations, block reviews), each with its own normalizer |
| `docs/experiments.md` | 1,287 lines, ~18k tokens | 12 | the workflow and queue, followed by every experiment's full writeup, including ones already implemented or lost |

**Change.** Move code without changing behaviour, splitting it by the
concern that changes together:

- **`App.tsx`** — lane tables (`TIMELINE_KEYS`, `SPARSE_LANE_ARTIFACT`,
  `CANVAS_LANES`, `canvasLaneHasData`) → `timeline/laneConfig.ts`;
  `formatClock` / `formatSecondsFixed` → a util; `SongPicker` → its own file;
  the hooks → custom hooks, one per concern (transport, drawer, song load,
  proposals, run analysis); the JSX → layout components. `App` only wires
  these together.
- **`laneContent.ts`** — one module per lane family (reference/hints,
  sections, vocal, rhythm, energy/gestures). `laneContent.ts` keeps the
  registry and `buildLaneBlocks` and re-exports the rest, so imports and
  tests stay unchanged.
- **`vite.config.ts`** — one module per endpoint under `ui/server/`, holding
  its file-path helper and normalizer; the config only registers them.
- **`experiments.md`** — keeps the workflow, the queue and the open entries.
  Entries that were implemented or measured-and-lost move to
  `docs/archive/`, leaving a one-line pointer.

Don't split finer than one concern per file: if a typical change has to open
five small files, it costs more reads than one large one.

| | |
| --- | --- |
| Writes | none (no artifact or contract change) |
| Reads changed | `ui/src/App.tsx`, `ui/src/timeline/laneContent.ts`, `ui/vite.config.ts` + new modules; `docs/experiments.md`, `docs/archive/` |
| Done when | the `ui/` test suite and `npm run build` pass with no test file edited except import paths; `App.tsx` ≤ 400 lines; no new module > 400 lines; the UI loads a song and saves a hint as before |

---

## Bugs

### Open

- **`crash` over-fires on bright hats/rides.** The v3.4 crash/hat split
  (drums-stem 6–16 kHz brilliance gate on GM 42) labels steady bright
  patterns as crashes: 17 of 23 songs publish > 15 crashes/min (up to 108/min,
  *Fascination*; *Cinderella* 186, in 2-beat streams through whole sections),
  where real crashes are a few accents per section. The operator rejected
  both *Cinderella* crash-run proposals: 222.37 is "one crash accent to bring
  the vocals", and the chorus crashes span its first 30 bars rather than 3.
  Plausible only where sparse (*Rapture* 5.6/min, *Armin* 1.9/min). A crash
  must be an isolated accent — a decaying broadband hit, not one in a regular
  stream — tested on the same per-hit spectral shape as item 2's kick check.
  Addressed by item 2 (a third sibling check), until then no consumer should
  treat `crash` as an accent cue.
