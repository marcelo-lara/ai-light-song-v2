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
            record("S2.6 get_song_overview(McpFull) returns without error",
                   "DEFER", f"not-implemented until items 9-10 — {_tool_text(ov)!r}")

            det = await session.call_tool(
                "get_detail",
                {"song": "McpFull - Fixture", "scope": "time_window",
                 "interval_ms": 20},
            )
            record("S2.7 get_detail(McpFull, window) returns dense frames",
                   "DEFER", f"not-implemented until items 9-10 — {_tool_text(det)!r}")

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
    # The F2-F4 honesty and detail-read checks require response shaping.
    record("F2-F4 honesty / detail-read contract checks", "DEFER",
           "require get_song_overview / get_detail payloads — v3.1 items 9-10")
    return _finish()


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP regression entry points")
    parser.add_argument("suite", choices=["smoke-test", "full-regression"])
    args = parser.parse_args()
    sys.path.insert(0, str(MCP_DIR))
    return smoke_test() if args.suite == "smoke-test" else full_regression()


if __name__ == "__main__":
    raise SystemExit(main())
