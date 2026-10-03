"""Named regression entry points for the `mcp/` server.

    python mcp/tests/run.py smoke-test
    python mcp/tests/run.py full-regression

An executor invokes these by name and reads the printed PASS / FAIL / DEFER
lines. Every check is binary and prints its observed value. Exit code is 0 only
when no check FAILed (a DEFER does not fail the run). Spec: see
docs/reference/mcp-regression.md.

Checks that need response shaping (`get_song_overview` / `get_detail` returning
real payloads) are DEFERRED here — that code lands in v3.1 items 9-10. They are
listed so the gap is visible, not silently skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = MCP_DIR / "tests" / "fixtures" / "analysis"
SERVER = MCP_DIR / "server.py"
EXPECTED_TOOLS = [
    "list_songs",
    "get_song_overview",
    "get_detail",
    "propose_hint",
    "request_analysis",
    "get_analysis_progress",
    "get_watcher_status",
    "get_structure_hint_brief",
    "write_structure_hint",
    "get_verdict_brief",
    "write_verdict_pass",
    "write_verdict_check",
]

_RESULTS: list[tuple[str, str, str]] = []


def record(check: str, status: str, observed: str) -> None:
    _RESULTS.append((check, status, observed))
    print(f"{status:5s} {check}\n      observed: {observed}")


def _tool_text(result) -> str:
    parts = []
    for block in getattr(result, "content", []) or []:
        parts.append(getattr(block, "text", str(block)))
    return " ".join(parts)


def _tool_json(result):
    """The tool's structured return value (dict/list), from structured_content
    or, failing that, the JSON text block."""
    sc = getattr(result, "structured_content", None)
    if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
        return sc["result"]
    if sc is not None:
        return sc
    return json.loads(_tool_text(result))


async def _run_stdio_checks() -> None:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    # v3.7 item 10 — propose_hint writes a queue file
    # under the song directory, so the stdio session points at a throwaway
    # copy of the fixtures (under the writable /data mount) rather than the
    # committed, read-only fixtures at FIXTURE_ROOT (under the :ro /app
    # mount). Every check below reads the same content either way.
    writable_root = Path("/data/.mcp_smoke_fixture_copy")
    if writable_root.exists():
        shutil.rmtree(writable_root)
    shutil.copytree(FIXTURE_ROOT, writable_root)

    # v3.8 item 3 — request_analysis checks for a `<song>.mp3` under
    # MCP_SONGS_ROOT before queuing a run; a throwaway songs root with one
    # stub audio file exercises both the "audio present, not yet analysed"
    # and "no audio at all" branches without touching the real mount.
    writable_songs_root = Path("/data/.mcp_smoke_songs_copy")
    if writable_songs_root.exists():
        shutil.rmtree(writable_songs_root)
    writable_songs_root.mkdir(parents=True)
    (writable_songs_root / "McpUnanalysed - Fixture.mp3").write_bytes(b"stub-audio-bytes")
    # A 0-byte placeholder (matches the real songs mount's `authoring-*.mp3`
    # files) and a real, non-empty file for an already-fully-analysed song —
    # neither should ever appear in request_analysis's "unanalysed audio"
    # error listing (S3.15 below).
    (writable_songs_root / "authoring-placeholder.mp3").write_bytes(b"")
    (writable_songs_root / "McpFull - Fixture.mp3").write_bytes(b"already analysed")

    env = dict(os.environ)
    env["MCP_ANALYSIS_ROOT"] = str(writable_root)
    env["MCP_SONGS_ROOT"] = str(writable_songs_root)
    # v3.10 item 11 — a heartbeat path that never exists, so the watcher
    # reads `down` regardless of any real watcher running on the host.
    env["MCP_WATCHER_HEARTBEAT"] = "/data/.mcp_smoke_no_heartbeat"
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)

    try:
        await _run_stdio_checks_against(params, writable_root)
    finally:
        shutil.rmtree(writable_root, ignore_errors=True)
        shutil.rmtree(writable_songs_root, ignore_errors=True)


async def _run_stdio_checks_against(params, writable_root: Path) -> None:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            record("S1.2 initialize handshake completes", "PASS",
                   f"server={getattr(init.server_info, 'name', '?')} "
                   f"v{getattr(init.server_info, 'version', '?')}")

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            status = "PASS" if names == EXPECTED_TOOLS else "FAIL"
            record("S1.3 tools/list == list_songs, get_song_overview, get_detail, "
                   "propose_hint, request_analysis, "
                   "get_analysis_progress, get_watcher_status, get_structure_hint_brief, "
                   "write_structure_hint, get_verdict_brief, write_verdict_pass, write_verdict_check", status, str(names))

            # S1.4 — stray stdout would have broken the handshake above.
            record("S1.4 no stray stdout (proxy: handshake + list succeeded)",
                   "PASS", "clean stdio framing")

            songs_res = await session.call_tool("list_songs", {})
            songs = (songs_res.structured_content or {}).get("result", [])
            got = sorted(s["song_name"] for s in songs)
            want = sorted(["McpFull - Fixture", "McpDegenerate - Fixture",
                           "McpPartial - Fixture"])
            complete = all(
                s["song_name"] is not None and s["bpm"] is not None
                and s["duration"] is not None for s in songs
            )
            status = "PASS" if got == want and complete else "FAIL"
            record("S2.5 list_songs -> 3 fixtures, each song_name/bpm/duration non-null",
                   status, json.dumps(songs))

            ov = await session.call_tool("get_song_overview",
                                         {"song": "McpFull - Fixture"})
            status = "PASS" if not ov.is_error else "FAIL"
            record("S2.6 get_song_overview(McpFull) returns without error",
                   status, f"is_error={ov.is_error} bytes={len(_tool_text(ov))}")

            det = await session.call_tool(
                "get_detail",
                {"song": "McpFull - Fixture", "start_ms": 0, "end_ms": 3000,
                 "interval_ms": 20},
            )
            frames = 0
            if not det.is_error:
                dense = (_tool_json(det) or {}).get("dense") or {}
                frames = dense.get("frame_count", 0)
            status = "PASS" if not det.is_error and frames > 0 else "FAIL"
            record("S2.7 get_detail(McpFull, 0-3000ms, 20ms) returns dense frames",
                   status, f"is_error={det.is_error} frame_count={frames}")

            unknown = await session.call_tool("get_song_overview",
                                              {"song": "no-such-song-xyz"})
            text = _tool_text(unknown)
            status = "PASS" if unknown.is_error and "no-such-song-xyz" in text else "FAIL"
            record("S3.8 unknown song errors with the name in the message",
                   status, repr(text))

            partial = await session.call_tool("get_song_overview",
                                              {"song": "McpPartial - Fixture"})
            text = _tool_text(partial)
            status = "PASS" if partial.is_error and "sections.json" in text else "FAIL"
            record("S3.9 McpPartial errors naming the missing file (sections.json)",
                   status, repr(text))

            # v3.7 item 10 — empty evidence is rejected and writes nothing.
            empty_evidence = await session.call_tool(
                "propose_hint",
                {"song": "McpFull - Fixture", "start": 10.0, "end": 12.0,
                 "title": "Drop payoff", "summary": "loudness spike",
                 "evidence": ""},
            )
            queue_path = writable_root / "McpFull - Fixture" / "reference" / "proposals" / "pending.json"
            status = "PASS" if empty_evidence.is_error and not queue_path.exists() else "FAIL"
            record("S3.10 propose_hint with empty evidence errors and writes nothing",
                   status, f"is_error={empty_evidence.is_error} queue_exists={queue_path.exists()}")

            # Two calls append two distinct entries, neither overwriting the other.
            first = await session.call_tool(
                "propose_hint",
                {"song": "McpFull - Fixture", "start": 10.0, "end": 12.0,
                 "title": "Drop payoff", "summary": "loudness spike",
                 "evidence": "loudness.json shows a 6dB step at 10.0s"},
            )
            second = await session.call_tool(
                "propose_hint",
                {"song": "McpFull - Fixture", "start": 14.0, "end": 15.0,
                 "title": "Second", "summary": "second hint",
                 "evidence": "gesture build overlaps this window"},
            )
            first_id = (_tool_json(first) or {}).get("id") if not first.is_error else None
            second_id = (_tool_json(second) or {}).get("id") if not second.is_error else None
            queue = json.loads(queue_path.read_text()) if queue_path.is_file() else {}
            ids = [p.get("id") for p in queue.get("proposals", [])]
            ok = (
                not first.is_error and not second.is_error
                and first_id is not None and second_id is not None
                and first_id != second_id
                and ids == [first_id, second_id]
            )
            status = "PASS" if ok else "FAIL"
            record("S3.11 two propose_hint calls append two distinct pending.json entries",
                   status, f"ids={ids}")

            # v3.8 item 3 — request_analysis / get_analysis_progress.
            already = await session.call_tool(
                "request_analysis", {"song": "McpFull - Fixture"},
            )
            text = _tool_text(already)
            status = "PASS" if already.is_error and "get_song_overview" in text else "FAIL"
            record("S3.12 request_analysis refuses an already-analysed song",
                   status, repr(text))

            requested = await session.call_tool(
                "request_analysis", {"song": "McpUnanalysed - Fixture"},
            )
            req_payload = _tool_json(requested) if not requested.is_error else {}
            request_path = (
                writable_root / "McpUnanalysed - Fixture" / "artifacts" / "_run_request.json"
            )
            status = (
                "PASS"
                if not requested.is_error
                and req_payload.get("status") == "requested"
                and request_path.is_file()
                else "FAIL"
            )
            record("S3.13 request_analysis on unanalysed-but-audible song writes a request",
                   status, f"is_error={requested.is_error} payload={req_payload}")

            queued = await session.call_tool(
                "get_analysis_progress", {"song": "McpUnanalysed - Fixture"},
            )
            queued_payload = _tool_json(queued) if not queued.is_error else {}
            status = "PASS" if not queued.is_error and queued_payload.get("status") == "queued" else "FAIL"
            record("S3.14 get_analysis_progress reports queued right after a fresh request",
                   status, f"is_error={queued.is_error} payload={queued_payload}")

            no_audio = await session.call_tool(
                "request_analysis", {"song": "no-such-audio-xyz"},
            )
            text = _tool_text(no_audio)
            status = (
                "PASS"
                if no_audio.is_error and "no-such-audio-xyz" in text
                and "McpUnanalysed - Fixture" in text
                # A 0-byte placeholder and an already-analysed song's audio
                # must never be offered as "unanalysed" — orchestrator review.
                and "authoring-placeholder" not in text
                and "McpFull - Fixture" not in text
                else "FAIL"
            )
            record("S3.15 request_analysis with no audio errors, listing unanalysed "
                   "non-empty not-yet-analysed stems only",
                   status, repr(text))

            never_requested = await session.call_tool(
                "get_analysis_progress", {"song": "McpNeverRequested - Fixture"},
            )
            text = _tool_text(never_requested)
            status = "PASS" if never_requested.is_error and "request_analysis" in text else "FAIL"
            record("S3.16 get_analysis_progress with no request errors, pointing at request_analysis",
                   status, repr(text))

            stale_request_dir = writable_root / "McpStale - Fixture" / "artifacts"
            stale_request_dir.mkdir(parents=True, exist_ok=True)
            (stale_request_dir / "_run_request.json").write_text(
                json.dumps({"song": "McpStale - Fixture",
                            "requested_at": "2000-01-01T00:00:00Z"}) + "\n",
                encoding="utf-8",
            )
            stale = await session.call_tool(
                "get_analysis_progress", {"song": "McpStale - Fixture"},
            )
            stale_payload = _tool_json(stale) if not stale.is_error else {}
            status = "PASS" if not stale.is_error and stale_payload.get("status") == "not_started" else "FAIL"
            record("S3.17 a request older than the threshold reports not_started",
                   status, f"is_error={stale.is_error} payload={stale_payload}")

            # Orchestrator review fix 2 — song-name validation before any path is built.
            traversal = await session.call_tool(
                "request_analysis", {"song": "../escaped-song"},
            )
            text = _tool_text(traversal)
            escaped_dir = writable_root.parent / "escaped-song"
            status = "PASS" if traversal.is_error and not escaped_dir.exists() else "FAIL"
            record("S3.18 request_analysis rejects a path-traversal song name, writes nothing",
                   status, f"is_error={traversal.is_error} escaped_dir_exists={escaped_dir.exists()}")

            # Orchestrator review fix 1 — a stale terminal progress (failed, finished
            # before a newer request) must not be read back verbatim forever.
            retry_dir = writable_root / "McpRetry - Fixture" / "artifacts"
            retry_dir.mkdir(parents=True, exist_ok=True)
            (retry_dir / "_run_progress.json").write_text(
                json.dumps({
                    "song": "McpRetry - Fixture", "status": "failed", "stage": "measure-loudness",
                    "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
                    "finished_at": "2020-01-01T00:05:00Z", "error": "boom",
                }) + "\n",
                encoding="utf-8",
            )
            fresh_requested_at = (
                datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            )
            (retry_dir / "_run_request.json").write_text(
                json.dumps({"song": "McpRetry - Fixture",
                            "requested_at": fresh_requested_at}) + "\n",
                encoding="utf-8",
            )
            retry = await session.call_tool(
                "get_analysis_progress", {"song": "McpRetry - Fixture"},
            )
            retry_payload = _tool_json(retry) if not retry.is_error else {}
            status = "PASS" if not retry.is_error and retry_payload.get("status") == "queued" else "FAIL"
            record("S3.19 a stale failed progress is ignored once a newer request exists",
                   status, f"is_error={retry.is_error} payload={retry_payload}")

            # Orchestrator review round 2 — a 0-byte placeholder counts as no audio.
            placeholder = await session.call_tool(
                "request_analysis", {"song": "authoring-placeholder"},
            )
            text = _tool_text(placeholder)
            status = "PASS" if placeholder.is_error and "No audio found" in text else "FAIL"
            record("S3.20 request_analysis refuses a 0-byte placeholder audio file",
                   status, repr(text))

            # v3.10 item 11 — force re-run + watcher status.
            ws = await session.call_tool("get_watcher_status", {})
            ws_payload = _tool_json(ws) if not ws.is_error else {}
            status = (
                "PASS" if not ws.is_error and ws_payload.get("status") == "down"
                and ws_payload.get("last_heartbeat") is None
                and ws_payload.get("age_s") is None else "FAIL"
            )
            record("S3.21 get_watcher_status is down with no heartbeat file",
                   status, f"payload={ws_payload}")

            forced = await session.call_tool(
                "request_analysis", {"song": "McpFull - Fixture", "force": True},
            )
            forced_payload = _tool_json(forced) if not forced.is_error else {}
            forced_path = (
                writable_root / "McpFull - Fixture" / "artifacts" / "_run_request.json"
            )
            status = (
                "PASS" if not forced.is_error
                and forced_payload.get("status") == "requested"
                and forced_payload.get("watcher") == "down"
                and forced_path.is_file() else "FAIL"
            )
            record("S3.22 request_analysis(force=True) re-runs an analysed song, reports watcher",
                   status, f"is_error={forced.is_error} payload={forced_payload}")

            # v3.10 item 7 — structure hint tools.
            hint_path = (writable_root / "McpUnanalysed - Fixture" / "reference"
                         / "pre-analysis" / "structure.json")
            good = {
                "schema_version": "1.1", "song_name": "McpUnanalysed - Fixture",
                "generated_at": "2026-10-01",
                "track": {"artist": "A", "title": "T", "version": "extended",
                          "remixer": None, "version_duration_s": 400},
                "genre": {"family": "edm", "subgenre": "big_room", "bpm": 128},
                "shape": {
                    "drops": {"value": 2, "basis": "stated", "source": 0, "quote": "Two drops."},
                    "chorus_is_drop": {"value": None, "basis": None, "source": None, "quote": None},
                    "has_build_ups": {"value": True, "basis": "inferred", "source": 0,
                                      "quote": "Builds into each drop."},
                    "vocals": "chops"},
                "confidence": 0.7,
                "sources": [{"url": "https://example.com", "title": "x"}],
            }
            brief = await session.call_tool(
                "get_structure_hint_brief", {"song": "McpUnanalysed - Fixture"})
            bp = _tool_json(brief) if not brief.is_error else {}
            prompt = await session.get_prompt(
                "structure_hint", {"song": "McpUnanalysed - Fixture"})
            prompt_text = " ".join(
                getattr(m.content, "text", "") for m in prompt.messages)
            ok = (not brief.is_error and bp.get("existing") is None
                  and bp.get("brief") == prompt_text
                  and "never write a time" in bp.get("brief", "").lower())
            record("S3.23 get_structure_hint_brief on an unanalysed song with audio: "
                   "brief == structure_hint prompt, existing null",
                   "PASS" if ok else "FAIL", f"is_error={brief.is_error}")

            bad_enum = {**good, "genre": {**good["genre"], "family": "polka"}}
            no_src = {**good, "sources": []}
            timed = {**good, "shape": {**good["shape"], "drop_time": 61.0}}
            refusals = []
            for label, payload in (("enum", bad_enum), ("sources", no_src), ("time", timed)):
                res = await session.call_tool(
                    "write_structure_hint",
                    {"song": "McpUnanalysed - Fixture", "hint": payload})
                refusals.append((label, res.is_error, _tool_text(res)[:80]))
            ok = all(r[1] for r in refusals) and not hint_path.exists()
            record("S3.24 write_structure_hint refuses unknown enum, no sources and a "
                   "time key, writing nothing", "PASS" if ok else "FAIL", str(refusals))

            wrote = await session.call_tool(
                "write_structure_hint",
                {"song": "McpUnanalysed - Fixture", "hint": good})
            again = await session.call_tool(
                "get_structure_hint_brief", {"song": "McpUnanalysed - Fixture"})
            ok = (not wrote.is_error and hint_path.is_file()
                  and not again.is_error and _tool_json(again).get("existing") == good)
            record("S3.25 a valid hint is written and round-trips through existing",
                   "PASS" if ok else "FAIL", f"is_error={wrote.is_error}")

            unknown = await session.call_tool(
                "get_structure_hint_brief", {"song": "No Such Song"})
            record("S3.26 get_structure_hint_brief on a song with no analysis and no "
                   "audio errors", "PASS" if unknown.is_error else "FAIL",
                   _tool_text(unknown)[:80])

            # v3.11 item 23 - second-pass tools: brief == prompt, and without a
            # verdict file every one of them errors (nothing is invented).
            vb = await session.call_tool("get_verdict_brief", {"song": "McpFull - Fixture"})
            vp = await session.get_prompt("verdict_pass", {"song": "McpFull - Fixture"})
            wp = await session.call_tool(
                "write_verdict_pass", {"song": "McpFull - Fixture", "results": {"drops": {}}})
            wc = await session.call_tool("write_verdict_check", {
                "song": "McpFull - Fixture", "field": "drops", "claim": "x",
                "evidence": {}, "cannot_settle": "x", "question": "x?"})
            queue = writable_root / "McpFull - Fixture" / "reference" / "proposals" / "pending.json"
            ok = (vb.is_error and wp.is_error and wc.is_error and not any(e.get("type") == "verdict_check" for e in (json.loads(queue.read_text())["proposals"] if queue.exists() else []))
                  and "second pass" in " ".join(getattr(m.content, "text", "") for m in vp.messages).lower())
            record("S3.27 verdict tools error without a verdict file and write nothing; "
                   "verdict_pass prompt served", "PASS" if ok else "FAIL",
                   f"errors={[vb.is_error, wp.is_error, wc.is_error]} queue_exists={queue.exists()}")


def _check_build() -> None:
    # If this harness is running, the image built and the SDK imported.
    try:
        import mcp  # noqa: F401
        record("S1.1 docker compose build mcp (proxy: SDK imports in-container)",
               "PASS", f"mcp SDK importable from {Path(mcp.__file__).parent}")
    except Exception as exc:  # pragma: no cover
        record("S1.1 docker compose build mcp", "FAIL", repr(exc))


def _check_exposure() -> None:
    forbidden = ("artifacts" + "/", "reference" + "/")
    hits = []
    for path in sorted(MCP_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(frag in text for frag in forbidden):
            hits.append(path.name)
    status = "PASS" if not hits else "FAIL"
    record("S4.10 exposure guard: no inner-folder path in mcp/ module source",
           status, f"scanned={[p.name for p in sorted(MCP_DIR.glob('*.py'))]} hits={hits}")


def _check_readonly_mount() -> None:
    # v3.7 item 10 — the /data mount changed from :ro to read-write so
    # propose_hint can append to a song's own proposals
    # queue file (docker-compose.yml's mcp service). The server's read-only
    # guarantee is now enforced entirely in code — loaders.py's top-level-only
    # reads, proposals.py's queue-file-only writes — rather than by the bind
    # mount; S4.10's exposure guard is what actually holds that boundary. This
    # check now asserts the mount IS writable: a probe failing here would mean
    # item 10's tools cannot function at all.
    root = Path(os.environ.get("MCP_ANALYSIS_ROOT", "/data/analysis"))
    probe = root.parent / ".mcp_write_probe"
    try:
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        record("S4.11 /data mount is writable (propose_*/write_structure_hint can write their bounded files)",
               "PASS", f"write to {probe} succeeded")
    except OSError as exc:
        record("S4.11 /data mount is writable (propose_*/write_structure_hint can write their bounded files)",
               "FAIL", f"{type(exc).__name__}: {exc}")


def _check_determinism() -> None:
    from loaders import list_songs

    a = json.dumps(list_songs(FIXTURE_ROOT), sort_keys=False)
    b = json.dumps(list_songs(FIXTURE_ROOT), sort_keys=False)
    status = "PASS" if a == b else "FAIL"
    record("F1.2 list_songs is byte-identical across two calls", status,
           f"len={len(a)}")


def _check_snapshot() -> None:
    from loaders import list_songs

    snap = MCP_DIR / "tests" / "__snapshots__" / "list_songs__fixture_root.json"
    if not snap.is_file():
        record("F1.1 golden snapshot list_songs__fixture_root.json matches",
               "FAIL", f"missing {snap}")
        return
    current = json.dumps(list_songs(FIXTURE_ROOT), indent=2, ensure_ascii=False) + "\n"
    status = "PASS" if current == snap.read_text(encoding="utf-8") else "FAIL"
    record("F1.1 golden snapshot list_songs__fixture_root.json matches", status,
           f"{len(current)} bytes")


def _overview_text(song: str) -> str:
    from serializers import build_song_overview

    payload = build_song_overview(song, root=FIXTURE_ROOT)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _check_overview_snapshots() -> None:
    for song in ["McpFull - Fixture", "McpDegenerate - Fixture"]:
        snap = MCP_DIR / "tests" / "__snapshots__" / f"get_song_overview__{song}.json"
        if not snap.is_file():
            record(f"F1.3 snapshot get_song_overview__{song}", "FAIL", f"missing {snap}")
            continue
        current = _overview_text(song)
        status = "PASS" if current == snap.read_text(encoding="utf-8") else "FAIL"
        record(f"F1.3 snapshot get_song_overview__{song}", status, f"{len(current)} bytes")


_DETAIL_SNAP_CASES = {
    "section_scope": dict(section_id="section-002"),
    "gesture_scope": dict(gesture_id="gesture-001"),
    "window_3s_20ms": dict(start_ms=0, end_ms=3000, interval_ms=20),
    "window_3s_100ms": dict(start_ms=0, end_ms=3000, interval_ms=100),
    "window_over_cap": dict(start_ms=0, end_ms=6000),
    # v3.7 item 3/5 — the `bars` scope selector.
    "bars_scope": dict(bars=[3, 4]),
}


def _check_detail_snapshots() -> None:
    from serializers import build_detail

    for name, kwargs in _DETAIL_SNAP_CASES.items():
        snap = MCP_DIR / "tests" / "__snapshots__" / f"get_detail__{name}.json"
        if not snap.is_file():
            record(f"F1.4 snapshot get_detail__{name}", "FAIL", f"missing {snap}")
            continue
        payload = build_detail("McpFull - Fixture", root=FIXTURE_ROOT, **kwargs)
        current = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        status = "PASS" if current == snap.read_text(encoding="utf-8") else "FAIL"
        record(f"F1.4 snapshot get_detail__{name}", status, f"{len(current)} bytes")


def _check_f1_beats_block() -> None:
    """v3.6 item 9: get_detail's structural view carries an undecimated
    `beats` block scoped to the resolved span — its row count must equal the
    number of beats actually inside that span, no more, no fewer."""
    from serializers import build_detail

    beats_doc = json.loads(
        (FIXTURE_ROOT / "McpFull - Fixture" / "beats.json").read_text()
    )
    resp = build_detail("McpFull - Fixture", root=FIXTURE_ROOT, section_id="section-002")
    span = resp["span"]
    expected = [
        b for b in beats_doc["beats"]
        if span["start"] <= b["time"] <= span["end"]
    ]
    rows = resp["structural"]["beats"]["rows"]
    ok = len(rows) == len(expected) and 0 < len(rows) < len(beats_doc["beats"])
    record("F1.5 get_detail beats block count == beats actually inside the span",
           "PASS" if ok else "FAIL",
           f"rows={len(rows)} expected={len(expected)} total_song_beats={len(beats_doc['beats'])}")

    # Present past the 5 s dense cap too — the one deliberate exception.
    over = build_detail("McpFull - Fixture", root=FIXTURE_ROOT, start_ms=0, end_ms=6000)
    record("F1.6 beats block present past the 5 s dense cap (dense withheld, beats not)",
           "PASS" if over["dense"] is None and over["structural"]["beats"]["rows"] else "FAIL",
           f"dense={over['dense']} beat_rows={len(over['structural']['beats']['rows'])}")


def _check_f1_all_ten_required() -> None:
    """Every one of loaders.REQUIRED_TOP_LEVEL_FILES is required — a song
    missing any single one errors naming that file. No degraded/optional path
    for any of the 10 (v3.6 item 9, v3.12 item 33)."""
    import shutil
    import tempfile

    from loaders import REQUIRED_TOP_LEVEL_FILES, MissingTopLevelFileError, resolve_song_dir

    ok_count = 0
    for missing in REQUIRED_TOP_LEVEL_FILES:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            song_dir = tmp_path / "Probe - Song"
            shutil.copytree(FIXTURE_ROOT / "McpFull - Fixture", song_dir)
            (song_dir / missing).unlink()
            try:
                resolve_song_dir("Probe - Song", root=tmp_path)
                ok = False
                observed = "no error raised"
            except MissingTopLevelFileError as exc:
                ok = missing in str(exc)
                observed = str(exc)
            if ok:
                ok_count += 1
            else:
                record(f"F1.7 missing {missing} errors naming it", "FAIL", observed)
    record("F1.7 all 10 required top-level files individually enforced",
           "PASS" if ok_count == len(REQUIRED_TOP_LEVEL_FILES) else "FAIL",
           f"{ok_count}/{len(REQUIRED_TOP_LEVEL_FILES)} named correctly")


def _check_f3_detail() -> None:
    from serializers import DetailScopeError, build_detail

    def _d(**kw):
        return build_detail("McpFull - Fixture", root=FIXTURE_ROOT, **kw)

    # F3.13 — a span over 5 s returns the structural view, no dense frames, cap named.
    over = _d(start_ms=0, end_ms=6000)
    ok = (
        over["dense"] is None
        and "dense_withheld" in over
        and "5" in over["dense_withheld"]["reason"]
        and bool(over["structural"]["sections"]["rows"])
    )
    record("F3.13 over-cap span -> structural view, no dense frames, cap named",
           "PASS" if ok else "FAIL",
           f"dense={over['dense']} reason={over.get('dense_withheld', {}).get('reason', '')!r}")

    # F3.14 — a span at exactly 5 s is accepted.
    exact = _d(start_ms=0, end_ms=5000)
    record("F3.14 a span at exactly 5 s is accepted (dense frames returned)",
           "PASS" if exact["dense"] and exact["dense"]["frame_count"] > 0 else "FAIL",
           f"frame_count={(exact['dense'] or {}).get('frame_count')}")

    # F3.15 — interval finer than the floor errors, naming it.
    try:
        _d(start_ms=0, end_ms=3000, interval_ms=10)
        record("F3.15 interval_ms below the 20 ms floor errors, naming the floor",
               "FAIL", "no error raised")
    except DetailScopeError as exc:
        record("F3.15 interval_ms below the 20 ms floor errors, naming the floor",
               "PASS" if "20" in str(exc) else "FAIL", repr(str(exc)))

    # F3.16 — interval_ms=100 returns one fifth the frames of interval_ms=20.
    fine = _d(start_ms=0, end_ms=3000, interval_ms=20)["dense"]["frame_count"]
    coarse = _d(start_ms=0, end_ms=3000, interval_ms=100)["dense"]["frame_count"]
    record("F3.16 interval_ms=100 returns one fifth the frames of interval_ms=20",
           "PASS" if coarse == fine // 5 else "FAIL", f"20ms={fine} 100ms={coarse}")

    # F3.17 — decimation preserves the transient peak (chunk-averaging, not dropping).
    win = dict(start_ms=12500, end_ms=14500)
    raw_peak = max(f["values"][0] for f in _d(**win, interval_ms=20)["dense"]["frames"])
    coarse_dense = _d(**win, interval_ms=100)["dense"]
    coarse_peak = max(f["values"][0] for f in coarse_dense["frames"])
    ok = coarse_dense["decimation"] == "pair-averaging" and coarse_peak >= raw_peak * 0.99
    record("F3.17 decimation preserves the window's transient peak (averaging)",
           "PASS" if ok else "FAIL",
           f"raw_peak={raw_peak} decimated_peak={coarse_peak} mode={coarse_dense['decimation']}")

    # F3.18 — zero or two scopes error, no precedence rule.
    n_err = 0
    for kw in ({}, dict(section_id="section-002", gesture_id="gesture-001")):
        try:
            _d(**kw)
        except DetailScopeError:
            n_err += 1
    record("F3.18 zero or two scope selectors error (no precedence rule)",
           "PASS" if n_err == 2 else "FAIL", f"{n_err}/2 raised")

    # F3.19 — sources narrows the stem set, returned in the published order.
    got = _d(start_ms=0, end_ms=3000, sources=["vocals", "bass"])["dense"]["sources"]
    record("F3.19 sources narrowing returns the requested stems in stable order",
           "PASS" if got == ["bass", "vocals"] else "FAIL", str(got))


def _check_f2_honesty() -> None:
    from serializers import build_song_overview

    VOCAB = {"essentia", "allin1", "omnizart", "demucs", "gestures",
             "human", "inference", "unknown", "arrangement_state",
             # v3.7 item 3/6 — section_id attributed against published sections.json.
             "sections",
             # v3.12 items 32-34 — `role` and the bar_features fields.
             "light_changes"}

    full = build_song_overview("McpFull - Fixture", root=FIXTURE_ROOT)
    degen = build_song_overview("McpDegenerate - Fixture", root=FIXTURE_ROOT)

    # F2.4 — field_sources present per published block, values in the vocabulary.
    fs_blocks = [full["identity"]["field_sources"], full["grid"]["field_sources"],
                 full["sections"]["field_sources"], full["gestures"]["field_sources"],
                 full["arrangement"]["field_sources"],
                 full["human_hints"]["field_sources"],
                 full["light_changes"]["field_sources"]]
    bad = [v for fs in fs_blocks for v in (fs or {}).values() if v not in VOCAB]
    record("F2.4 overview field_sources present, values in vocabulary",
           "PASS" if all(fs_blocks) and not bad else "FAIL",
           f"blocks={sum(1 for b in fs_blocks if b)}/6 bad_values={bad}")

    # F2.6 — function_status "unknown" surfaced on the degenerate song.
    st = [r["function_status"] for r in degen["sections"]["rows"]]
    record("F2.6 function_status 'unknown' surfaced on McpDegenerate",
           "PASS" if st and all(s == "unknown" for s in st) else "FAIL", str(st))

    # F2.7 — same_label_as grouping carries the caveat.
    cav = full["sections"].get("caveat", "")
    record("F2.7 same_label_as caveat present wherever sections are grouped",
           "PASS" if "label repetition" in cav else "FAIL", repr(cav))

    # F2.8 — downbeat_confidence null passed through (count, not a rendered 0).
    n_null = degen["grid"]["downbeats_null_confidence"]
    n_db = degen["grid"]["downbeat_count"]
    record("F2.8 downbeat_confidence null passed through on McpDegenerate",
           "PASS" if n_null == n_db and n_db > 0 else "FAIL",
           f"null={n_null} of {n_db} downbeats")

    # F2.9 — the grid note qualifies the downbeat phase, not the beat time.
    note = full["grid"]["downbeat_note"]
    record("F2.9 downbeat note qualifies the downbeat phase, not the beat time",
           "PASS" if "downbeat" in note and "beat time" not in note else "FAIL",
           repr(note))

    # F2.10 — a gesture missing a phase reports it absent, not zero-filled.
    rows = full["gestures"]["rows"]
    ok = all("phases_absent" in r and "phases_present" in r for r in rows)
    record("F2.10 gesture phases reported present/absent, never zero-filled",
           "PASS" if ok else "FAIL",
           str([(r["gesture_id"], r["phases_absent"]) for r in rows]))

    # F2.11 — no response names a drop directly.
    blob = json.dumps(full).lower()
    record("F2.11 no response names a drop directly",
           "PASS" if "drop" not in blob else "FAIL",
           "no 'drop' token" if "drop" not in blob else "'drop' present")


def _check_f4_budget() -> None:
    full_text = _overview_text("McpFull - Fixture")
    size = len(full_text.encode("utf-8"))
    # Ceiling 6900 since v3.9 item 1 (vocal_cadence.json's compact overview
    # block and per-section fields; see test_overview_budget_mcpfull_under_7kb).
    record("F4.20 get_song_overview(McpFull) under the 6900-byte budget",
           "PASS" if size < 6900 else "FAIL", f"{size} bytes")

    record("F4.21 no host path in the overview (no string starting /data/)",
           "PASS" if "/data/" not in full_text else "FAIL",
           "clean" if "/data/" not in full_text else "leak")

    from serializers import build_song_overview
    ov = build_song_overview("McpFull - Fixture", root=FIXTURE_ROOT)

    def _max_list_len(node) -> int:
        if isinstance(node, list):
            return max([len(node)] + [_max_list_len(v) for v in node], default=0)
        if isinstance(node, dict):
            return max([_max_list_len(v) for v in node.values()], default=0)
        return 0

    longest = _max_list_len(ov)
    # The fixture beat grid is 48 rows; any list that long in the overview is a
    # leaked series. Sections/gestures/hints lists are single digits.
    has_beatlist = "beats" in ov["grid"] or longest > 16
    record("F4.22 get_song_overview never returns the full beat list",
           "PASS" if not has_beatlist else "FAIL",
           f"longest list in payload = {longest}")


def _finish() -> int:
    failed = [c for c, s, _ in _RESULTS if s == "FAIL"]
    deferred = [c for c, s, _ in _RESULTS if s == "DEFER"]
    passed = [c for c, s, _ in _RESULTS if s == "PASS"]
    print("\n" + "=" * 60)
    print(f"PASS {len(passed)}   FAIL {len(failed)}   DEFER {len(deferred)}")
    if deferred:
        print("deferred (response shaping — v3.1 items 9-10):")
        for c in deferred:
            print(f"  - {c}")
    if failed:
        print("FAILED:")
        for c in failed:
            print(f"  - {c}")
    return 1 if failed else 0


def smoke_test() -> int:
    _check_build()
    asyncio.run(_run_stdio_checks())
    _check_exposure()
    _check_readonly_mount()
    return _finish()


def full_regression() -> int:
    _check_build()
    asyncio.run(_run_stdio_checks())
    _check_exposure()
    _check_readonly_mount()
    _check_determinism()
    _check_snapshot()
    _check_overview_snapshots()
    _check_detail_snapshots()
    _check_f2_honesty()
    _check_f3_detail()
    _check_f4_budget()
    _check_f1_beats_block()
    _check_f1_all_ten_required()
    return _finish()


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP regression entry points")
    parser.add_argument("suite", choices=["smoke-test", "full-regression"])
    args = parser.parse_args()
    sys.path.insert(0, str(MCP_DIR))
    return smoke_test() if args.suite == "smoke-test" else full_regression()


if __name__ == "__main__":
    raise SystemExit(main())
