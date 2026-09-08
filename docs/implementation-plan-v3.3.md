# Implementation Plan — v3.3

Status: complete, implemented and validated in-container (2026-09-08).
Depends on: [product-refinement-v3.3.md](product-refinement-v3.3.md), [mcp-definition.md](mcp-definition.md), [reference/mcp-regression.md](reference/mcp-regression.md).
Scope: [mcp/](../mcp/) only. No analyzer stage work, no UI work, no new signal generation.

## How this plan is worked

- Validate each item, then commit it on its own. For each item: implement, run required container checks, tick checkboxes only after passing evidence, then commit that item before the next one. The commit subject must match the item name exactly.
- Use the recommendation; only a genuinely blocking decision stops an item. If a minor question appears, apply this plan's locked decision and continue. Only add a D item when any assumption would make work wrong.

## Locked decisions (no open questions)

- D3.1: Canonical client topology is remote Docker over SSH for both repos.
  - Canonical command shape:
    - ssh s2.local -T -- docker compose -f <absolute-repo-path>/docker-compose.yml run --rm -T mcp
- D3.2: Item 0 measurement target for get_song_overview is <= 1000 tokens on longest song and on _test_song.
- D3.3: If Item 0 exceeds target, implement get_song_overview(scope="brief").
  - brief keeps identity, grid summary, section rows (without description prose), gesture rows, arrangement rows, transition rows, hint counts.
  - brief excludes full hint prose and section description prose.
- D3.4: Sparse-event row cap for get_detail is 512 rows per sparse block.
  - Applies to drum-event rows returned in detail.
  - On cap hit: keep explicit refusal shape (never silent truncation) and return structural view.
- D3.5: arrangement_state absence must be explicit in overview payload.
  - Required shape:
    - "arrangement": {"available": false, "reason": "missing_top_level_file", "missing_file": "arrangement_state.json", "note": "song analysed before v3.2; re-run pipeline to populate"}
- D3.6: Gesture anchor in overview is impact_time.
  - If no impact phase exists for a gesture, impact_time is null and no synthetic fallback is generated.

## Build order

1. 0. Measure baseline token cost
2. 1. get_detail serves drum onsets
3. 2. Separate dense-cap and sparse-cap rules
4. 4. Add whole-song impact anchors
5. 5. Make arrangement_state absence explicit
6. 3. Make get_song_overview the concept-pass read
7. 6. Restate boundary in definition docs
8. 7. Close contract-change-v3.1 as superseded
9. S3.1. Align cross-repo client invocation docs

---

## 0. Measure baseline token cost

Goal: record actual call sizes before changing payload shapes.

- [x] Add a deterministic measurement script at [mcp/tests/measure_tokens.py](../mcp/tests/measure_tokens.py).
  - Input songs:
    - longest song directory under data/analysis by info.duration
    - _test_song
  - Calls measured:
    - get_song_overview(song)
    - get_detail(song, section_id=<first section>) structural-only path
    - get_detail(song, gesture_id=<first gesture>) dense 5s path
  - Output format:
    - chars and approx tokens (chars/4)
    - written to [docs/reference/mcp-token-baseline-v3.3.md](reference/mcp-token-baseline-v3.3.md)
- [x] Add a make target or documented command in [reference/mcp-regression.md](reference/mcp-regression.md) for repeatable reruns.

Validation

- [x] Run in container and capture baseline numbers for both songs.
- [x] Baseline document committed with exact observed values.

Commit subject: 0. Measure baseline token cost

## 1. get_detail serves drum onsets

Goal: return drum events in detail responses from top-level drum_events.json.

- [x] Update [mcp/loaders.py](../mcp/loaders.py): include drum_events.json in required top-level files.
- [x] Update [mcp/serializers.py](../mcp/serializers.py):
  - load drum_events.json in build_detail
  - return drum rows in resolved span: time, event_type, confidence
  - add window summary counts so caller can distinguish no events vs no data.
- [x] Keep exposure rule unchanged: top-level files only.

Validation

- [x] Update [mcp/tests/test_detail.py](../mcp/tests/test_detail.py) for drum rows and summary counts.
- [x] Update affected snapshots under [mcp/tests/__snapshots__](../mcp/tests/__snapshots__).
- [x] Run smoke-test and full-regression in container.

Commit subject: 1. get_detail serves drum onsets

## 2. Separate dense-cap and sparse-cap rules

Goal: keep 5s cap for dense loudness, apply row cap for sparse events.

- [x] Update [mcp/serializers.py](../mcp/serializers.py):
  - keep dense loudness cap at 5s unchanged
  - apply sparse row cap (D3.4) independent of span
  - for section_id scope, return sparse events across full section span when under cap
  - on sparse cap hit, use explicit withheld/refusal block naming cap and observed row count.
- [x] Keep interval_ms floor logic and chunk-averaging behavior unchanged.

Validation

- [x] Add tests in [mcp/tests/test_detail.py](../mcp/tests/test_detail.py):
  - section span >5s still returns sparse events
  - dense withheld over cap while sparse is present
  - sparse-cap-hit path is explicit and not silently truncated.
- [x] Update [reference/mcp-regression.md](reference/mcp-regression.md) F3 checks to include sparse-cap assertions.

Commit subject: 2. Separate dense-cap and sparse-cap rules

## 4. Add whole-song impact anchors

Goal: make overview usable as a whole-song anchor map.

- [x] Update [mcp/serializers.py](../mcp/serializers.py):
  - add impact_time per gesture row from impact phase timestamp
  - keep existing gesture span and peak intensity fields
  - keep honesty caveats and no synthetic drop field.
- [x] Keep grouping by gesture_id unchanged.

Validation

- [x] Add tests in [mcp/tests/test_overview.py](../mcp/tests/test_overview.py):
  - impact_time present when impact phase exists
  - impact_time null when impact phase missing.
- [x] Update overview snapshots.

Commit subject: 4. Add whole-song impact anchors

## 5. Make arrangement_state absence explicit

Goal: absence is surfaced as an explicit gap, not key omission.

- [x] Update [mcp/serializers.py](../mcp/serializers.py):
  - always return arrangement key
  - when file exists: current compact blocks
  - when missing: required explicit unavailable block (D3.5)
  - include note that arrangement_state is strong for who-is-playing, weak for drop staging.

Validation

- [x] Update [mcp/tests/test_overview.py](../mcp/tests/test_overview.py) to assert explicit missing block on McpDegenerate fixture.
- [x] Update overview snapshots and honesty checks in [reference/mcp-regression.md](reference/mcp-regression.md).

Commit subject: 5. Make arrangement_state absence explicit

## 3. Make get_song_overview the concept-pass read

Goal: concept pass uses this tool as single read, with optional brief scope only if needed by Item 0.

- [ ] If Item 0 <= 1000 tokens for both songs:
  - keep single overview shape; update docs only.
- [x] If Item 0 > 1000 tokens for either song:
  - add scope parameter to get_song_overview in [mcp/server.py](../mcp/server.py)
  - implement scope handling in [mcp/serializers.py](../mcp/serializers.py) per D3.3
  - keep one tool only; no new tool.
- [x] Ensure same_label_as caveat remains attached in both densities.

Validation

- [x] Add tests in [mcp/tests/test_overview.py](../mcp/tests/test_overview.py) for scope behavior.
- [x] Re-run measurement script and append post-change table to [docs/reference/mcp-token-baseline-v3.3.md](reference/mcp-token-baseline-v3.3.md).
- [x] Verify concept-pass read size target is met (or explain residual overage explicitly in doc).

Commit subject: 3. Make get_song_overview the concept-pass read

## 6. Restate boundary in definition docs

Goal: document both directions of the boundary.

- [x] Update [docs/mcp-definition.md](mcp-definition.md):
  - keep cue-authoring prohibition unchanged
  - add reciprocal statement: downstream server no longer reads data/analysis
  - state consequence: unpublished top-level signal cannot reach cue authoring.
- [x] Update [docs/reference/downstream-contract.md](reference/downstream-contract.md) wording to match single song-comprehension surface.

Validation

- [x] Doc review: no conflicting statements remain.

Commit subject: 6. Restate boundary in definition docs

## 7. Close contract-change-v3.1 as superseded

Goal: close pending handoff note with final outcome.

- [x] Replace pending-delivery framing in [docs/contract-change-v3.1.md](contract-change-v3.1.md) with superseded outcome.
- [x] Add archival note file [docs/archive/contract-change-v3.1-superseded.md](archive/contract-change-v3.1-superseded.md) summarizing:
  - downstream did not migrate file readers
  - downstream deleted analysis readers in v1.5
  - v3.x handoffs are tool-shape handoffs.
- [x] Link from [docs/mcp-definition.md](mcp-definition.md) to the superseded note.

Validation

- [x] No remaining doc text claims v3.1 handoff is pending.

Commit subject: 7. Close contract-change-v3.1 as superseded

## S3.1. Align cross-repo client invocation docs

Goal: both repos publish the same canonical invocation topology.

- [x] Update [docs/mcp-definition.md](mcp-definition.md) invocation section to canonical remote SSH form (D3.1) and include required -f path.
- [x] Update [../../ai-dmx-light-render/docs/mcp-server-definition.md](../../ai-dmx-light-render/docs/mcp-server-definition.md) only if wording diverges after v1.5 edits.
- [x] Keep both required -T flags documented.

Validation

- [x] Side-by-side diff review confirms topology/flags/path requirements match.

Commit subject: S3.1. Align cross-repo client invocation docs

---

## Required container validation commands (per item)

- [x] docker compose build mcp
- [x] docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test
- [x] docker compose run --rm --no-deps -T --entrypoint python mcp -m pytest mcp/tests/test_overview.py mcp/tests/test_detail.py mcp/tests/test_server_tools.py
- [x] For tool-surface or payload-shape changes: docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py full-regression

## Status checklist

- [x] Item 0 complete
- [x] Item 1 complete
- [x] Item 2 complete
- [x] Item 4 complete
- [x] Item 5 complete
- [x] Item 3 complete
- [x] Item 6 complete
- [x] Item 7 complete
- [x] Item S3.1 complete

## Completion gate

- [x] [mcp-definition.md](mcp-definition.md) reflects shipped v3.3 behavior.
- [x] [product-refinement-v3.3.md](product-refinement-v3.3.md) item outcomes are marked and linked to commits.
- [x] Full regression passes in container on committed fixtures.
