# Product refinement — v3.8

**Status: drafting.**

---

## 1. One-click analysis trigger from the debugger — `ui/`, new host-side component

**Current behaviour.** Running `./analyze` for a song is a host/operator CLI
step only (`CLAUDE.md` "Running things"). The debugger UI cannot start it: the
`ui` service's dev container (the only build with any write capability — prod
is static nginx) has no Docker socket and no Docker CLI. A Docker-socket
mount was already tried for the same shape of problem — the correction-proposal
approve flow re-running an analyzer stage — and reverted (`implementation-plan
v3.7`, item 11, decision D11.1): it is root-equivalent host access, judged too
broad a grant for what it bought, and it did not even work on this host
(rootless Docker, "permission denied"). The fallback that shipped instead is a
static reminder banner naming the command for the operator to run by hand
(`PendingProposalsPanel.tsx`'s `rerun-reminder`).

**Change.** Add a new host-side watcher — a plain process the operator runs
directly on the host, **not** inside any container. Because it runs natively
on the host it already has the host's own `docker` CLI available and needs no
Docker-socket grant into any container — the exact root-equivalent access
D11.1 rejected does not arise here. It watches for a run request and executes
`docker compose run --rm app ./analyze --song "<path>"` on the operator's
behalf. The `ui` container's role stays exactly what it is today: it writes
intent, never executes anything itself.

- **Request.** The UI's existing write path (dev-only PUT middleware in
  `vite.config.ts`) writes a request file, e.g.
  `data/analysis/<song>/artifacts/_run_request.json` (`{"song": "...",
  "requested_at": "..."}`), through the same `mkdir` + `writeFile` pattern the
  six existing `reference/human/` writers use. This is a **new** write
  contract (outside the six vite.config.ts already names) — flagged here
  rather than added silently.
- **Execution.** The watcher serializes globally — one job at a time across
  the whole corpus, not just per song, since analysis is GPU-bound
  (`--device cuda`) and concurrent runs would contend for it. A request for a
  song while another song's run is in flight waits queued rather than
  starting in parallel or being rejected. The watcher runs the analyze
  command and writes progress to a sibling file, e.g. `_run_progress.json`
  (fields: `status` [`queued`/`running`/`done`/`failed`], `stage` [current
  pipeline stage name, from `STAGE_PIPELINE_IDS`], `started_at`,
  `finished_at`, `error` when failed). Deletes (or marks terminal) the request
  file once picked up, so a stale request is never re-run on watcher restart.
- **Progress in the UI.** The UI polls `_run_progress.json` the same way it
  reads any other `data/` file today (via the static `/data` mount / autoindex
  read path) — no new read endpoint needed, only the new write path above.
  Shows current stage and queued/running/done/failed state on the selected
  song.
- **Persistence.** `_run_progress.json` is not a delivery artifact — it lives
  under `artifacts/`, never top level, so the MCP server never sees it
  (mcp-exposes-only-top-level-song-json). It is overwritten per run, not
  appended; no history of past runs is kept by this feature.

**Why a new component, not the ui container.** The `ui` container is a Vite
dev-server middleware plugin (dev) and static nginx (prod) — neither can spawn
processes, and D11.1 already established that giving the `ui` container
Docker-socket access is a decision that needs to be surfaced and made
deliberately, not folded into an unrelated feature. Running the watcher
natively on the host instead of in a container sidesteps that grant
altogether rather than re-litigating it.

**Out of scope.** Run history/log retention beyond the current run;
triggering anything other than a full `./analyze --song` (no per-stage
trigger from this UI surface — that remains the existing manual-command
reminder pattern).

| | |
| --- | --- |
| Writes | `artifacts/_run_request.json` (UI, new), `artifacts/_run_progress.json` (host-side watcher, new) |
| Reads changed | `ui/vite.config.ts` (new PUT endpoint), `ui/src/` (trigger button + progress poll/display), new host-side watcher process/service |
| Done when | clicking the button on a selected song starts `./analyze --song` on the host, the UI shows live stage/queued/running/done/failed progress without a page reload, and a click for a song while another song's run is in flight queues rather than starting a second concurrent run |

---

## 2. MCP can request an analysis for a song with no artifacts — `mcp/server.py`

**Current behaviour.** The MCP server is read-only over `data/analysis/{song}`
plus the two `propose_*` write tools (queue-only, to
`reference/proposals/pending.json`). If the authoring LLM asks about a song
that has never been analyzed, there is nothing to request a run — the song
has no top-level JSON for the server to serve at all.

**Change.** A new MCP tool, `request_analysis(song)`, reusing item 1's
request/progress files rather than a separate mechanism:

- Checks whether the song already has artifacts. If it does, the tool refuses
  and points the caller at the existing read tools instead of starting a
  redundant run.
- If not, writes `artifacts/_run_request.json` (the same file item 1's UI
  button writes) and returns immediately — it does not block waiting for the
  run to finish.
- The response tells the LLM the run has started, that analysis takes real
  time, and to poll roughly once a minute rather than immediately re-calling.
- A second tool, `get_analysis_progress(song)`, reads item 1's
  `_run_progress.json` and reports `status`/`stage` — this is the poll target
  the response instructs the caller to use. If a request file exists but no
  progress file has appeared within a short threshold (e.g. 2 minutes) —
  meaning no watcher picked it up — the tool reports a distinct `not_started`
  status rather than leaving the caller indistinguishable from a normal
  `queued` wait. An honest "nothing is watching this" beats an indefinite
  poll loop (no-silent-fallbacks).

**Why reuse item 1's files.** One request/progress mechanism, not two —
whether the run was started from the debugger button or from the MCP tool,
the same host-side watcher and the same progress file serve both.

**Out of scope.** Re-analyzing a song that already has artifacts (that stays
an operator action, same as any other rerun); the MCP triggering anything
narrower than a full `./analyze --song` run.

| | |
| --- | --- |
| Writes | `artifacts/_run_request.json` (MCP, same file as item 1) |
| Reads changed | `mcp/server.py` (two new tools) |
| Done when | calling `request_analysis` on an unanalyzed song starts a run and returns a poll instruction; `get_analysis_progress` reports `queued`/`running` while the run is pending or in flight, `done`/`failed` after, and `not_started` if no watcher has picked up the request within the threshold; calling `request_analysis` on an already-analyzed song is refused |
