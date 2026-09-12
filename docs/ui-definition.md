# UI definition — the artifact debugger

`ui/` is an **internal engineering tool**, played against the song. It is not a
product surface, and it must not redefine the stable contract under
`data/analysis/{song}/`.

Runbook for the visual regression suite:
[`reference/ui-regression.md`](reference/ui-regression.md).

## The two purposes

Everything the debugger does serves one of these. A proposed feature that serves
neither does not belong here.

### 1. Debug and review findings

Inspect what the pipeline claimed, against the audio, at the instant it claims
it. Timing, confidence and provenance inspection; artifact-to-artifact
comparison; raw JSON; auditioning unpromoted experiment proposals beside
hand-authored truth.

### 2. Author time-synced human hints

The debugger is where a human hint comes into existence. Three routes in, all
producing the same kind of hint:

| Route | What happens |
| --- | --- |
| **Promoted from an inference** | a block in an inference or experiment lane is turned into a hint — the operator heard it, agrees, and keeps it |
| **Human-reviewed** | an existing hint is corrected — its span dragged, its text rewritten |
| **Created by ear** | a hint marked from scratch against the waveform, backed by nothing the pipeline found |

This is the only place the operator's ground truth is authored, which makes it
the origin of everything downstream that carries `source: "human"`.

Out of scope: authoring or editing lighting output, acting as an end-user
playback product, and redefining the top-level artifact contract.

Debugger browser code lives in `ui/` only — never under `src/`.

## Reads: unrestricted

**The debugger may read anything it wants** — anywhere under `data/`, at any
depth: `artifacts/`, `reference/`, the source audio, intermediates nothing else
consumes. It is a debugger; a file it cannot open is a bug it cannot diagnose.

The exposure rule that confines the `mcp/` server to top-level `*.json` does
**not** apply here, and the lane table below is a description of what it reads
today, never a list of what it is allowed to read.

## Runtime

A separate Compose service named `ui`; the analyzer `app` service stays the only
runtime for inference and GPU work. The `ui` service must not reuse the analyzer
container.

| | |
| --- | --- |
| Dev server | Vite, live reload from `ui/src/` |
| Production | Nginx, `listen 8080` |
| App | Preact under `ui/src/` |
| Port | container `8080` → host `9090` |
| Mount | `./data:/data` |

```bash
docker compose up ui            # dev, live reload
docker compose build ui         # production image
# then open http://localhost:9090
```

## The write rule — load-bearing

**The debugger is read-only against generated data.** No snapshots, no caches,
no derived JSON, no overrides, no helper files into `data/analysis/`.

The only four writable paths:

- `data/analysis/{song}/reference/human/human_hints.json` — explicit `Save`
- `data/analysis/{song}/reference/human/song_facts.json` — explicit `Save`
- `data/analysis/{song}/reference/human/block_energy.json` — explicit `Save`.
  The operator's 1–5 `energy` / `tension` rating per `human_hints.json` block,
  joined by `hint_id`, edited in the Human Hints events panel (v3.4 item 4). Two
  independent axes: a "close to silence" block is lowest-energy,
  highest-tension. A block is unrated when it is absent from `ratings`; the
  segmented selectors show an explicit no-segment-pressed state, never a
  defaulted `1`. Written by `PUT /api/block-energy/<song>` (dev-server only,
  like the hint editor — production Nginx has no handler). Nothing in `src/` or
  `mcp/` reads it.
- `data/analysis/{song}/reference/human/lyric_validations.json` — **per-click**,
  not `Save` (v3.4 item 5 / D6). `{ schema_version, song_name, validated_ids:
  [int] }`: the ids of the Moises word tokens whose timing the operator has
  hand-verified with the ✔ button in the Moises Lyrics events panel. An
  **overlay** on `reference/moises/lyrics.json` — the lane shows a listed token
  at confidence `1` (a value Moises never emits) with a distinct tint; the
  Moises file itself is never edited and stays inference-only. Written by
  `PUT /api/lyric-validations/<song>` (dev-server only), which sends the full
  `validated_ids` array on each toggle and replaces the file. The per-click
  cadence is a deliberate divergence from the explicit-`Save` pattern the other
  three writers use — a rapid token-by-token pass should not need a Save button.
  Nothing in `src/` or `mcp/` reads it.

`Cancel` / closing a panel must never update the three explicit-`Save` files.
The dev-server
API enforces this at the mount level. A future workflow needing persisted
review data must be documented as a new contract, not added implicitly.

### A promoted hint is indistinguishable from a hand-marked one

`human_hints.json` is the operator's own hand-authored ground truth and must keep
reading that way, whichever of the three routes produced an entry.

- **Prefer no field at all** — a hint's content is the hint.
- Where something genuinely must be recorded, it is **one human-readable string
  aimed at the person who opens the file**, not a structured object aimed at a
  script. `captured_from` (e.g. `"allin1 Sections · experiments/allin1"`) is that
  field.
- `type` (`"hint"` | `"review"`) names which of the two the entry is: `"hint"`
  for one authored from scratch, `"review"` for one seeded from an
  experiment/event block to review or annotate a finding. It is editable in
  the hint editor's Type dropdown — not a hard link to the origin, just a
  reviewer-facing label — and tints the Human Hints lane block so a review
  entry reads apart from a hand-authored one on the timeline.
- Both keys are **omitted entirely** on a hand-authored hint with no note, so
  its shape is unchanged.
- No analyzer code reads either field. Do not design a field here around a
  machine consumer.

**The `field_sources` / `source` attribution on the generated delivery surface
stops at these files.** That convention exists so a *fused, machine-written*
value can say which producer won. `reference/human/` has exactly one producer —
the operator — and adding provenance machinery to it (to `human_hints.json`,
`song_facts.json`, `block_energy.json` or `lyric_validations.json`) would answer
a question nobody is asking while making the file harder to read by hand.

## Lanes

Lanes are the review surface, and any time-bearing experiment output gets one.
This table is **current state, not a permitted-reads list** — see "Reads:
unrestricted" above.

| Lane | Reads | Notes |
| --- | --- | --- |
| Sections | `sections.json` + `artifacts/section_segmentation/sections.json` | a `function_status: "contested"` section (v3.4 phase-3 energy contest) gets a distinct orange per-block tint (`sectionsContested`); its inspector card prints `function_status: contested` + `contested_by: energy` |
| Chord Regions | `artifacts/layer_a_harmonic.json` | |
| Gestures | `song_event_timeline.json` | |
| Arrangement State | `arrangement_state.json` | top-level published (v3.2); who is playing, per-stem RMS state changes |
| Human Hints | `reference/human/human_hints.json` (+ `reference/human/block_energy.json` for the per-block `energy`/`tension` rating controls in its events panel) | writable |
| Moises Lyrics | `reference/moises/lyrics.json` (+ `reference/human/lyric_validations.json` overlay) | read-only ground truth; blocks tinted by per-word confidence. Each word-token card in its events panel has a ✔ button (v3.4 item 5); a validated token shows at confidence `1` with the distinct `moisesLyricsValidated` tint in both the panel and the lane. `lyric_validations.json` is writable (per-click); `reference/moises/lyrics.json` is never edited |
| Drop Proposals | `reference/proposals/drop_impacts.json` | experiment |
| Character, Shadow | `reference/proposals/character.json` | experiment |
| 2. Texture Novelty | `reference/proposals/texture_novelty.json` | experiment (v3.4 item 6 — failed its kill condition, kept for one review pass) |
| 3. Phrase Periodicity | `reference/proposals/phrase_periodicity.json` | experiment (v3.4 item 7 — passed its kill condition) |
| 4. Structural vs Micro | `reference/proposals/structural_vs_micro.json` | experiment (v3.4 item 8 — failed its kill condition, kept for one review pass) |
| Vocal Phrases, Vocal Transcription | `reference/proposals/vocal_*.json` | experiment |
| Dense lanes | `essentia/fft_bands.json`, `essentia/fft_bands.bass.json`, `essentia/fft_bands.drums.json`, `essentia/fft_bands.harmonic.json`, `essentia/fft_bands.vocals.json`, `essentia/rms_loudness.json`, `essentia/loudness_envelope.json`, `symbolic_transcription/drum_events.json`, `artifacts/layer_c_energy.json` | four per-stem FFT lanes beside the mix lane; each fails loudly on a missing artifact |

**Badging rule.** A lane fed from `reference/proposals/` is unpromoted
experiment output and carries a `ph-flask` badge in its lane head and its
events-panel header. A lane fed from `reference/human/` or `reference/moises/`
is ground truth and carries no badge. A song without the backing file renders an
empty lane (and logs a `404`) rather than failing.

A lane is removed when its experiment is abandoned or promoted.

## Interaction state

Zoom, playhead, lane visibility, lane collapse and region selection are
**browser-local only**. Shared zoom spans 14–360 px/bar; at maximum zoom a long
song exceeds the ~32k-pixel canvas ceiling, so dense lanes hold their CSS width
and downscale the backing store instead.

The playhead stays visible across both zoom and playback. During playback, a
footer toggle ("Follow playhead", on by default) auto-scrolls to keep it
onscreen, and turns itself off the moment the reviewer scrolls manually.
While paused, zooming (buttons, slider or keyboard shortcut) keeps the
playhead pinned to the same screen pixel it occupied before the zoom, rather
than letting it drift off-screen; fit-to-width instead just scrolls the
playhead back into view if the new zoom pushed it out.
