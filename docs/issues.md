# Open issues

**Pending issues only** (a queue, not a history). Solving one means deleting its
entry in the same change; write anything durable into the relevant definition
doc first. An empty queue is not a claim that the analysis is in good shape —
see [`analysis-definition.md`](analysis-definition.md) "Known gaps".

Scope each entry to one problem, one validation target, and one success
condition — and make the success condition mean the *stage* improved, not that
one song stopped complaining.

Current focus song: `_test_song`
(`reference/human/human_hints.json`, `reference/moises/chords.json`,
`artifacts/validation/phase_1_report.json`).

## Open queue

### `gestures` — per-primitive precision has never been audited by ear

- **Status:** `pending`
- **Raised:** 2026-09-05, on closing the v3.0 release docs. This was the one
  risk the release accepted and did not discharge, and it is the largest
  unmeasured risk in the shipped pipeline.
- **Problem:** the gestures stage is scored on impact *recall* against seven
  hand-clicked impacts. A phantom primitive — a riser, a build or a tension
  span asserted where the music has none — does not move that metric at all,
  yet it fires a cue that contradicts the song. Nothing currently measures how
  often that happens.
- **Evidence to use:** every gesture phase in `song_event_timeline.json`
  carries its per-primitive evidence string, so the audit is possible against
  the shipped artifacts without re-running anything.
- **Validation target:** the four gold songs (`Titanium - David Guetta ft Sia`,
  `Armin - Revolution`, `Hideaway - Kiesza`, `_test_song`), auditioned in the
  debugger against the waveform.
- **Success condition:** a per-primitive precision figure exists for each
  gesture phase across the gold set, and either the false-positive rate is
  written into `CLAUDE.md` as a known bound, or the primitives responsible for
  the phantoms are tightened until it is.

### `get_song_overview` — prose budget on gesture-dense songs

- **Status:** `pending`
- **Raised:** 2026-09-06, closing v3.1 (decision D25, resolved-as-accepted).
- **Problem:** the committed token-budget gate is fixture-based — the
  `McpFull - Fixture` overview is 4283 bytes, under the 6144-byte ceiling. Real
  gesture-dense songs run larger: `Titanium` 13981 B, `Armin - Revolution`
  12644 B, `Hideaway` 10025 B, `_test_song` 7936 B — all over the 6 KB
  real-song target the plan set.
- **Why it was accepted, not fixed:** the size is driven by *structure*, not
  prose. On `Armin` the 31 grouped gesture rows are ~6.8 KB on their own —
  already over the target — and the 13 human-hint rows (~2.2 KB) are verbatim
  ground truth that the honesty rules forbid trimming. The genre `guidance` and
  section `description` prose is already short (~180 / ~30 chars); clipping it
  saves under 300 bytes and does not change the picture. Getting near 6 KB would
  mean cutting gesture structure or truncating hints, both of which the plan
  ruled out.
- **Options for a real fix:** a phase-code legend replacing repeated
  `phases_present` / `phases_absent` arrays; a compact gesture encoding; or
  making the overview paginate gestures and expose the rest via `get_detail`.
- **Success condition:** a gesture-dense gold song's `get_song_overview` is at
  or under 6 KB with every human hint still verbatim and every composite gesture
  still individually addressable — or the 6 KB target is formally replaced with
  a structure-aware budget in `mcp-definition.md`.

### Delivery surface — `hints.json` / `song_event_timeline.json` still embed host paths

- **Status:** `pending`
- **Raised:** 2026-09-06, phase-D handoff gate for v3.1. Found by re-running
  `build-ui-data` across all 21 songs and scanning every top-level file.
- **Problem:** the standing rule is "no absolute host path in any top-level
  file". v3.1 item 7 fixed `loudness.json` and item 8 fixed `info.json`, but two
  top-level files were never in a v3.1 item's scope and still carry a
  `generated_from` block with `/data/songs/…` and `/data/analysis/…/artifacts/…`
  paths: `hints.json` (written by `hints.py`) and `song_event_timeline.json`
  (written by `gestures.py`).
- **Not a response leak:** the `mcp/` serializers do not copy `generated_from`
  into any payload — `full-regression` F4.21 ("no string beginning `/data/`")
  passes. The committed fixtures are host-path-free, so the suites stay green.
  The leak is only in the raw published files a future consumer might read
  directly.
- **Fix:** the publish path for both files drops `generated_from` (matching item
  8's `info.json` decision — a client discovers files from the fixed layout, and
  the block pointed into `artifacts/` which is not exposable anyway), or rewrites
  it song-relative. Rebuild the MCP fixtures and re-run `full-regression`.
- **Success condition:** every top-level file across all 21 songs contains no
  string beginning `/data/`, asserted in `full-regression` against a fixture
  that would actually catch a regression.

### `ui-visual` — three items left open from the regression-suite handoff

- **Status:** `pending`
- **Raised:** 2026-09-05, on trimming the suite's own checklist out of
  [`reference/ui-regression.md`](reference/ui-regression.md).
- **Open items:**
  1. Decide the `_test_song` audio question. Interim: `RegFull` / `RegPartial`
     ship the real mp3; `_test_song` has none, so its baseline is the
     beat-pulse fallback. The open call is whether `RegFull` keeps the mp3 or
     moves to a pre-decoded peaks JSON.
  2. Fold the smoke-check list from `ui/README.HELPER_UI.md` into explicit
     assertions, so the README checklist and the suite cannot drift apart.
  3. Corner-pixel checks on `humanHints` / `sections` blocks; re-diff
     `song-full` after squaring the block corners.
- **Success condition:** all three resolved, or the suite's scope explicitly
  narrowed to exclude them.

