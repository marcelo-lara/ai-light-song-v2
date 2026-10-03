# Product refinement — v3.11

**Status: open, one item left.** Items 1-4 (version check, schema `1.1` evidence,
first-pass verdicts, second pass) shipped in v3.11; their current state lives in
`docs/analysis-definition.md` ("Pre-analysis structure hint"),
`docs/mcp-definition.md` and `docs/reference/artifacts.md`.

---

## Unshipped: the operator's answer on a `verdict_check`

**Open.** The debugger shows a `verdict_check` card with Confirm and Reject; the
answer is stored as `operator` on the verdict. The corpus run queued exactly one
check (*Hideaway - Kiesza* `chorus_is_drop`: "is the chorus a separate part from
where the bass and drum beat first comes in?").

| | |
| --- | --- |
| Done when | the operator confirms that check in the UI. A rejection could not be exercised: no second check exists on this corpus (every other refuted or unresolved verdict was settled by the second pass), so "one approved and one rejected" needs a future song |
| Related | first-pass `has_build_ups` counts only `Build-Up` labels, so loudness ramps are invisible to it (3 of 3 refuted, all `wrong: analysis`); a stage limitation noted in `analysis-definition.md`, not planned |
