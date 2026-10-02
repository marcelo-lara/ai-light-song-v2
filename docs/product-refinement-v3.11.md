# Product refinement — v3.11

**Status: open.** Makes the pre-analysis structure hint (v3.10 item 7) checkable:
evidence per claim, a version check, and verdicts against the audio.

---

## 1. Version check before the hint is trusted

**Change.** After a run, code compares the hint with the published `info.json`:
`track.version_duration_s` against `duration` (> 5 s apart is a mismatch) and
`genre.bpm` against `bpm` (> 3 % apart, half and double time counted as equal).
A mismatch sets `version_mismatch: true` in the verdict file (item 3) and every
consumer ignores `track.version` and `shape`. Today this is a note, not code.
A null duration or BPM is not a mismatch.

| | |
| --- | --- |
| Writes | `version_check` block of `reference/pre-analysis/verdict.json` |
| Reads changed | new `src/` stage after `info.json`; `docs/mcp-definition.md`, `artifacts.md` |
| Done when | the five songs listed in `analysis-definition.md` as duration-mismatched are flagged, and no other song is |

## 2. Per-field evidence — schema 1.1

**Change.** Each `shape` field becomes `{value, basis, source, quote}`:
`basis` is `stated` (a source says it) or `inferred` (derived from stated facts,
e.g. `chorus_is_drop` from a described hook-loop chorus); `source` is an index
into `sources[]`; `quote` is the supporting sentence. `value: null` means no
evidence. The brief allows `inferred` values but refuses a value with no quote;
a chat-assistant answer is not a source. `sources[]` stays `{url, title}`;
`confidence` stays as the overall figure. `1.0` hints stay readable.

Why: "never guess" left `drops`, `chorus_is_drop` and `has_build_ups` null on
all 27 songs. Labelled inference with a quote fills them without admitting
bare guesses.

| | |
| --- | --- |
| Writes | `reference/pre-analysis/structure.json` (`schema_version "1.1"`) |
| Reads changed | `mcp/structure_hint.py` (brief, validator), `docs/mcp-definition.md`, `artifacts.md` |
| Done when | a `shape` value without `basis` and `quote` is refused naming the field; the corpus is re-hinted and the share of non-null `shape` fields is reported |

## 3. Verdict per field against the audio

**Change.** A stage after analysis writes `reference/pre-analysis/verdict.json`:
one verdict per `shape` field and for `genre.bpm`, each `confirmed`, `refuted`
or `unresolved`, with the published evidence it used (section ids and counts,
never times). `drops` is checked against `Drop` and `Extended Drop` sections,
`has_build_ups` against `Build-Up` sections, `chorus_is_drop` against whether
the song's `Drop` sections carry a sung vocal, `vocals` against the vocal
stem. Disagreeing or missing evidence is `unresolved`, never forced. A hint
under `version_mismatch` gets no shape verdicts. Nothing in the analysis
reads the verdict; refutations are the signal for tuning the research brief.

| | |
| --- | --- |
| Writes | `reference/pre-analysis/verdict.json`, only by the stage |
| Reads changed | new `src/` stage reading `sections.json`, `arrangement_state.json`, `info.json`; docs |
| Done when | every corpus song has a verdict file and the verdict counts per field are reported |

## 4. Second pass over the verdicts

**Change.** A second, independent pass re-derives each `refuted` and
`unresolved` verdict from different evidence than item 3 used (stem
entries/exits, `drum_density`, `dropouts`, the loudest stretches), read through
`get_detail` by the client. Where it agrees, the verdict gains `checked: true`;
where it disagrees, `contested: true` with both readings. Only contested
verdicts go to the operator. The pass never edits the hint or the analysis.

Why: item 3 can be wrong in either direction (a mislabelled section refutes a
true hint); a second route to the same question catches that before the
research brief is tuned on it.

| | |
| --- | --- |
| Writes | `checked` / `contested` fields in `reference/pre-analysis/verdict.json`, by a code-scoped MCP write like `write_structure_hint` |
| Reads changed | `mcp/` (new write tool, brief), `docs/mcp-definition.md` |
| Done when | on the corpus, every refuted or unresolved verdict is `checked` or `contested`, and the contested ones are listed for the operator |
