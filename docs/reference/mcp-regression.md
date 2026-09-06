# Reference — MCP server regression

How to prove the `mcp/` server still works. Two named suites:

| Suite | Runtime | When |
| --- | --- | --- |
| **`smoke-test`** | seconds | after **every** plan item, every commit that touches `mcp/`, and before any handoff |
| **`full-regression`** | minutes | before a release, before handing the server to a downstream consumer, and after any change to the tool surface or the delivery surface |

This guide is not tied to v3.1. It applies to the current implementation and
every future one — when a tool is added or reshaped, its checks are added here
in the same change.

Definition of the server: [`../mcp-definition.md`](../mcp-definition.md).
The UI's equivalent runbook: [`ui-regression.md`](ui-regression.md).

## The executor contract

These suites may be run by a low-reasoning executor. The guide removes the
judgement:

- The executor **follows steps and compares observed values to stated expected
  values.** It does not assess whether a response "looks reasonable".
- Every check is **binary** and carries its expected result inline. "The
  overview returns useful data" is not a check. "`sections[]` has length 7" is.
- If a step needs an expected value this guide does not give, that is a **spec
  defect to report back**, never a call for the executor to make.
- Report **every** check as pass/fail **with the observed value** — never a
  single overall verdict.

## Fixtures and determinism

**Generated analysis output is not committed to this repository** — `.gitignore`
keeps `data/analysis/*/**` except `reference/`. A suite pointed at a local
`data/analysis/` therefore compares against whatever the last pipeline run
produced, which is not a regression test.

So, as the UI suite already does with `tests/ui-visual/fixtures/`:

- **Frozen fixtures live in `mcp/tests/fixtures/analysis/<Fixture Song>/`** and
  are committed. They carry the full top-level file set and nothing else — no
  `artifacts/`, no `reference/`, because the server may not read those and a
  fixture containing them would hide a violation.
- **At least one fixture is fully populated.** Never let the only target be a
  degenerate song whose *correct* response is sparse — a real bug is then
  indistinguishable from the fixture. Name it in the fixture README.
- The required fixture set:

  | Fixture | Represents |
  | --- | --- |
  | `McpFull - Fixture` | fully populated: several sections, at least one complete gesture, human hints, all top-level files. **The primary baseline.** |
  | `McpDegenerate - Fixture` | `function_status: "unknown"` on every section, `downbeat_confidence: null` throughout — the honest-uncertainty path |
  | `McpPartial - Fixture` | a required top-level file absent — the explicit-error path |

- Keep them **small**: a short song, so `loudness.json` at the 20 ms floor is a
  few thousand frames, not millions. Fixtures are checked into git.
- **Byte-identical responses.** The same fixture and the same arguments must
  produce the same bytes on every run. Any ordering derived from a `set` or a
  dict iteration is a determinism bug, not a cosmetic one.
- Golden snapshots live in `mcp/tests/__snapshots__/`. They are **regenerated,
  not defended**: when a response shape changes deliberately, re-record in the
  same commit with a one-line justification per changed snapshot. They exist to
  catch *unintended* drift.

---

## `smoke-test`

Fast, and the gate on every item. Nothing here needs the full corpus.

### S1 — the server is alive

1. `docker compose build mcp` exits 0.
2. The server starts over stdio and completes an MCP `initialize` handshake.
3. `tools/list` returns exactly the tools the definition declares, by name.
4. The process writes nothing to stdout except MCP protocol frames — stray
   prints corrupt a stdio transport.

### S2 — it can answer

5. `list_songs()` against the fixture root returns all three fixtures, each with
   a non-null `song_name`, `bpm` and `duration`.
6. `get_song_overview("McpFull - Fixture")` returns without error.
7. `get_detail("McpFull - Fixture", start_ms=0, end_ms=3000, interval_ms=20)`
   returns dense frames.

> **Check 6 runs (v3.1 item 9).** `get_song_overview` returns a real payload.
> **Check 7 is DEFERRED until v3.1 item 10** — `get_detail` still validates its
> arguments and raises an explicit not-implemented error; the harness reports it
> as `DEFER` with the observed error text, never as pass. Checks 8 and 9 run.

### S3 — it fails honestly

8. An unknown song name errors, and the message contains the name asked for.
9. `McpPartial - Fixture` errors naming **the missing file** — never a partial
   response with silent gaps.

### S4 — the boundaries hold

10. The exposure guard passes: no occurrence of `artifacts/` or `reference/` in
    `mcp/`'s own source.
11. Writing to the mounted `/data` fails — the read-only bind is real, not
    assumed.

**Pass condition:** every check reported with its observed value; no `FAIL`.
Checks 6 and 7 are `DEFER` until v3.1 items 9-10 and do not gate.

Run it: `docker compose run --rm --no-deps -T --entrypoint python mcp
mcp/tests/run.py smoke-test` (exit 0 = no `FAIL`). `full-regression` adds the
determinism and snapshot checks and marks F2-F4 `DEFER` for the same reason.

---

## `full-regression`

Everything in `smoke-test`, plus the following. Run against all three fixtures
unless a check names one.

### F1 — snapshots and determinism

1. Every golden snapshot in `mcp/tests/__snapshots__/` matches byte for byte —
   `list_songs__fixture_root.json` (F1.1) and
   `get_song_overview__{McpFull,McpDegenerate} - Fixture.json` (F1.3).
2. Each tool called twice with identical arguments returns **byte-identical**
   output.
3. Snapshot coverage: every tool × every scope it accepts × each fixture.

> Snapshots are **regenerated, not defended** — regenerate them inside the
> container (`MCP_REGEN_SNAPSHOTS=1 pytest mcp/tests/test_overview.py` for the
> overview, or capture `run.py`'s serializer output) so byte-for-byte equality
> holds against the runtime, then commit with one line of justification each.

### F2 — the honesty obligations

These are the checks that matter most, because a response can be perfectly
well-formed and still lie. Each maps to an obligation in
[`../mcp-definition.md`](../mcp-definition.md).

4. `field_sources` is present on every response block derived from a published
   file, and every value in it is in the closed producer vocabulary.
5. A row that departs from its file's declared default carries its own `source`;
   a row that does not, does not. (No blanket per-row source maps — that is the
   token cost the encoding exists to avoid.)
6. `function_status: "unknown"` is surfaced as such on `McpDegenerate`, never
   smoothed into a confident label.
7. Wherever `same_label_as` groups sections, the response carries the
   "label repetition, not acoustic identity" caveat.
8. `downbeat_confidence: null` is passed through as `null` on `McpDegenerate` —
   not omitted, not defaulted to `0`, not rendered as a number.
9. A confidence is reported against the thing it measures: no response labels a
   downbeat-phase confidence as a confidence in the beat time.
10. A gesture missing a phase reports it **absent**, not zero-length and not
    interpolated.
11. No response names a drop directly — drops appear only as gesture phases or
    as a section-pair transition.
12. Every value in a response equals the value in the source top-level file. No
    silent rounding, rescaling or unit change.

### F3 — the detail-read contract

13. A resolved span **over 5 s** returns the structural view, contains **no**
    dense frames, and states the cap. It never truncates and never silently
    downsamples.
14. A span at exactly 5 s is accepted.
15. `interval_ms` finer than the published floor errors, naming the floor. It
    never silently upsamples.
16. `interval_ms=100` returns one fifth the frames of `interval_ms=20` over the
    same window.
17. Decimation preserves the window's peak value — averaging, not
    frame-dropping, so a transient is not lost.
18. Passing two scopes, or none, errors. There is no precedence rule.
19. `sources` narrowing returns exactly the stems asked for, in a stable order.

### F4 — token budget

20. The serialized `get_song_overview` for `McpFull - Fixture` is under its
    stated budget. Record the observed size in bytes on every run — a budget
    silently creeping upward is the failure this catches.
21. No response embeds an absolute host path (no string beginning `/data/`).
22. `get_song_overview` never returns the full beat list.

**Pass condition:** all of `smoke-test` plus F1–F4, each reported with its
observed value.

---

## When the tool surface changes

The server's tools are expected to be reshaped. That is routine, and this is the
routine:

1. Add or amend the checks in this guide **first**, so the expected values exist
   before the code does.
2. Re-record the affected snapshots in the same commit, one line of
   justification each.
3. Run `full-regression`, not just `smoke-test` — a tool-surface change is
   exactly the case where a distant honesty check breaks.
4. If a check here becomes untrue, delete it in the same change. A regression
   guide that documents behaviour the server no longer has is worse than no
   guide.

## Outstanding harness work

Tracked here until done; the suites are not fully runnable while any box is open.

- [x] Build `mcp/tests/fixtures/analysis/` and its generator script.
- [x] Capture the initial golden snapshots.
- [x] Wire `smoke-test` and `full-regression` as named entry points so an
      executor can invoke them by name rather than assembling checks by hand.
- [x] Keep `full-regression` fixture-based by default; the suite is intentionally
      deterministic and the committed fixtures are the validation source of truth.
      A local `data/analysis/` run is optional developer-only context, not a
      required regression gate.
