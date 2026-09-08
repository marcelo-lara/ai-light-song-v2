"""Measure serialized sizes for get_song_overview and get_detail.

Writes a simple baseline report to docs/reference/mcp-token-baseline-v3.3.md
and prints the same to stdout. Designed to run inside the repository or inside
the container used by the regression harness.

Usage (local):
    python mcp/tests/measure_tokens.py

Usage (container):
    docker compose run --rm --no-deps -T -e MCP_ANALYSIS_ROOT=/data/analysis \
      --entrypoint python mcp mcp/tests/measure_tokens.py
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
import sys

MCP_DIR = Path(__file__).resolve().parents[1]
# Ensure the mcp package directory is importable by name-based imports used in
# the repository modules (loaders, serializers).
sys.path.insert(0, str(MCP_DIR))

from loaders import list_songs, resolve_song_dir, load_top_level_json
from serializers import build_song_overview, build_detail

# Resolve analysis fixtures root robustly. Prefer an explicit fixtures
# directory under this repository but fall back to common alternatives.
def _find_fixtures_root() -> Path | None:
    # 1) Candidate relative to this file: repo_root / mcp/tests/fixtures/analysis
    p = Path(__file__).resolve()
    for up in range(0, 6):
        try:
            cand = p.parents[up] / "mcp" / "tests" / "fixtures" / "analysis"
        except Exception:
            continue
        if cand.is_dir():
            return cand
    # 2) Candidate relative to current working directory
    cwd = Path.cwd()
    cand = cwd / "mcp" / "tests" / "fixtures" / "analysis"
    if cand.is_dir():
        return cand
    # 3) Last resort: rely on the environment (used in container runs)
    env = Path("/data/analysis")
    if env.is_dir():
        return env
    return None

ROOT = _find_fixtures_root()
# If running with MCP_ANALYSIS_ROOT override, loaders.get_analysis_root will
# prefer the env var when resolving songs; the script defaults to the discovered ROOT.

def _find_output_path() -> Path:
    p = Path(__file__).resolve()
    for up in range(0, 6):
        repo_root = p.parents[up]
        cand = repo_root / "docs" / "reference"
        if cand.is_dir():
            return cand / "mcp-token-baseline-v3.3.md"
    # fallback to current working dir ./docs/reference
    cand = Path.cwd() / "docs" / "reference"
    if cand.is_dir():
        return cand / "mcp-token-baseline-v3.3.md"
    # last resort: create under repo root if writable
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "docs" / "reference" / "mcp-token-baseline-v3.3.md"

OUT_PATH = _find_output_path()


def _approx_tokens(chars: int) -> int:
    return max(1, chars // 4)


def _first_section_id(song_dir: Path) -> str | None:
    try:
        sec = load_top_level_json(song_dir, "sections.json")
        rows = sec.get("sections", [])
        if rows:
            return rows[0].get("section_id")
    except Exception:
        return None
    return None


def _first_gesture_id(song_dir: Path) -> str | None:
    try:
        tl = load_top_level_json(song_dir, "song_event_timeline.json")
        for e in tl.get("events", []):
            gid = e.get("gesture_id")
            if gid:
                return gid
    except Exception:
        return None
    return None


def measure_song(song_name: str, root: Path) -> dict:
    song_dir = resolve_song_dir(song_name, root=root)
    results = {"song": song_name}
    # overview
    ov = build_song_overview(song_name, root=root)
    ov_text = json.dumps(ov, indent=2, ensure_ascii=False)
    results["overview_chars"] = len(ov_text.encode("utf-8"))
    results["overview_tokens"] = _approx_tokens(results["overview_chars"]) 

    # detail: structural-only via first section
    sec_id = _first_section_id(song_dir)
    if sec_id:
        det_struct = build_detail(song_name, section_id=sec_id, root=root)
        text = json.dumps(det_struct, indent=2, ensure_ascii=False)
        results["detail_struct_section_id"] = sec_id
        results["detail_struct_chars"] = len(text.encode("utf-8"))
        results["detail_struct_tokens"] = _approx_tokens(results["detail_struct_chars"])
    else:
        results["detail_struct_section_id"] = None

    # detail: dense 5s via first gesture
    gid = _first_gesture_id(song_dir)
    if gid:
        det_dense = build_detail(song_name, gesture_id=gid, root=root)
        text = json.dumps(det_dense, indent=2, ensure_ascii=False)
        results["detail_dense_gesture_id"] = gid
        results["detail_dense_chars"] = len(text.encode("utf-8"))
        results["detail_dense_tokens"] = _approx_tokens(results["detail_dense_chars"])
    else:
        results["detail_dense_gesture_id"] = None

    return results


def main() -> int:
    root = ROOT
    if not root.is_dir():
        print(f"Analysis root not found at {root}. Try setting MCP_ANALYSIS_ROOT or run inside the container.")
        return 2

    songs = list_songs(root=root)
    if not songs:
        print("No songs discovered under analysis root.")
        return 2

    # pick longest by duration
    longest = max((s for s in songs if s.get("duration") is not None), key=lambda s: s["duration"], default=songs[0])
    longest_name = longest["song_name"]

    # fallback test song: prefer a short degenerate fixture if present
    names = [s["song_name"] for s in songs]
    test_song = "_test_song"
    if test_song not in names:
        # prefer McpDegenerate then McpPartial
        for cand in ("McpDegenerate - Fixture", "McpPartial - Fixture", "McpFull - Fixture"):
            if cand in names:
                test_song = cand
                break

    measured = []
    for s in (longest_name, test_song):
        print(f"Measuring: {s}")
        try:
            r = measure_song(s, root=root)
            measured.append(r)
        except Exception as exc:
            print(f"ERROR measuring {s}: {exc}")
            measured.append({"song": s, "error": str(exc)})

    # write report
    now = datetime.utcnow().isoformat() + "Z"
    lines = [f"# MCP token baseline v3.3\n\nGenerated: {now}\n\n"]
    for r in measured:
        lines.append(f"## {r.get('song')}\n")
        if r.get("error"):
            lines.append(f"ERROR: {r['error']}\n\n")
            continue
        lines.append(f"- overview: {r['overview_chars']} chars, approx {r['overview_tokens']} tokens\n")
        if r.get("detail_struct_section_id"):
            lines.append(f"- detail (section {r['detail_struct_section_id']}): {r['detail_struct_chars']} chars, approx {r['detail_struct_tokens']} tokens\n")
        else:
            lines.append(f"- detail (section): none available\n")
        if r.get("detail_dense_gesture_id"):
            lines.append(f"- detail (gesture {r['detail_dense_gesture_id']}): {r['detail_dense_chars']} chars, approx {r['detail_dense_tokens']} tokens\n")
        else:
            lines.append(f"- detail (gesture): none available\n")
        lines.append("\n")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("Baseline written to:", OUT_PATH)
    print("\n".join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
