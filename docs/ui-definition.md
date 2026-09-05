# UI definition — the artifact debugger

`ui/` is an **internal engineering tool** for inspecting pipeline output against
the song. It is not a product surface, and it must not redefine the stable
contract under `data/analysis/<Song - Artist>/`.

Runbook for the visual regression suite:
[`reference/ui-regression.md`](reference/ui-regression.md).

## What it is for

| In scope | Out of scope |
| --- | --- |
| Read-only visualization of generated artifacts | Writing files into `data/analysis/` (one exception below) |
| Timing, validation and provenance inspection | Authoring or editing lighting output |
| Artifact-to-artifact comparison | Acting as an end-user playback product |
| Raw JSON inspection | Redefining the top-level artifact contract |
| Audio playback for review context | |
| Auditioning experiment proposals against the song | |

Debugger browser code lives in `ui/` only — never under `src/`.

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

The only two writable paths, and only on an explicit `Save`:

- `data/analysis/<Song - Artist>/reference/human/human_hints.json`
- `data/analysis/<Song - Artist>/reference/human/song_facts.json`

`Cancel` must never update either file. The dev-server API enforces this at the
mount level. A future workflow needing persisted review data must be documented
as a new contract, not added implicitly.

## Lanes

Lanes are the review surface, and any time-bearing experiment output requires
experiment output to get one. Current lanes:

| Lane | Reads | Notes |
| --- | --- | --- |
| Sections | `artifacts/section_segmentation/sections.json` | |
| Chord Regions | `artifacts/layer_a_harmonic.json` | |
| Gestures | `song_event_timeline.json` | |
| Human Hints | `reference/human/human_hints.json` | writable |
| Moises Lyrics | `reference/moises/lyrics.json` | read-only ground truth; blocks tinted by per-word confidence |
| Drop Proposals | `reference/proposals/drop_impacts.json` | experiment |
| Character, Shadow | `reference/proposals/character.json` | experiment |
| Phrase Grid | `reference/proposals/grid.json` | experiment |
| Reactive Bands | `reference/proposals/reactive_bands.json` | experiment |
| Vocal Phrases, Vocal Transcription | `reference/proposals/vocal_*.json` | experiment |
| Dense lanes | `essentia/fft_bands.json`, `essentia/rms_loudness.json`, `essentia/loudness_envelope.json`, `symbolic_transcription/drum_events.json`, `artifacts/layer_c_energy.json` | |

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
