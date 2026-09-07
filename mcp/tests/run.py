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
import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = MCP_DIR / "tests" / "fixtures" / "analysis"
SERVER = MCP_DIR / "server.py"
EXPECTED_TOOLS = ["list_songs", "get_song_overview", "get_detail"]

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

    env = dict(os.environ)
    env["MCP_ANALYSIS_ROOT"] = str(FIXTURE_ROOT)
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            record("S1.2 initialize handshake completes", "PASS",
                   f"server={getattr(init.server_info, 'name', '?')} "
                   f"v{getattr(init.server_info, 'version', '?')}")

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            status = "PASS" if names == EXPECTED_TOOLS else "FAIL"
            record("S1.3 tools/list == list_songs, get_song_overview, get_detail",
                   status, str(names))

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
    root = Path(os.environ.get("MCP_ANALYSIS_ROOT", "/data/analysis"))
    probe = root.parent / ".mcp_write_probe"
    try:
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        record("S4.11 writing to the /data mount fails (read-only bind holds)",
               "FAIL", f"write to {probe} succeeded")
    except OSError as exc:
        record("S4.11 writing to the /data mount fails (read-only bind holds)",
               "PASS", f"{type(exc).__name__}: {exc}")


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

    VOCAB = {"essentia", "allin1", "harmonic", "omnizart", "demucs", "gestures",
             "genre", "human", "inference", "unknown", "arrangement_state"}

    full = build_song_overview("McpFull - Fixture", root=FIXTURE_ROOT)
    degen = build_song_overview("McpDegenerate - Fixture", root=FIXTURE_ROOT)

    # F2.4 — field_sources present per published block, values in the vocabulary.
    fs_blocks = [full["identity"]["field_sources"], full["grid"]["field_sources"],
                 full["sections"]["field_sources"], full["gestures"]["field_sources"],
                 full["arrangement"]["field_sources"],
                 full["human_hints"]["field_sources"]]
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
    record("F4.20 get_song_overview(McpFull) under the 6144-byte budget",
           "PASS" if size < 6144 else "FAIL", f"{size} bytes")

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
    return _finish()


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP regression entry points")
    parser.add_argument("suite", choices=["smoke-test", "full-regression"])
    args = parser.parse_args()
    sys.path.insert(0, str(MCP_DIR))
    return smoke_test() if args.suite == "smoke-test" else full_regression()


if __name__ == "__main__":
    raise SystemExit(main())
