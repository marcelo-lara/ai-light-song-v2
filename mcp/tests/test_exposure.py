"""The exposure rule as a failing test, not a convention.

The server may read `data/analysis/<song>/*.json` and nothing else. If a path
fragment that reaches an inner folder appears anywhere in the server's own
module source, this test fails.

Scope: `mcp/*.py` (server.py, loaders.py). Files under `mcp/tests/` are excluded
— fixtures and harness legitimately name inner folders to assert they are absent.
"""

from __future__ import annotations

from pathlib import Path

FORBIDDEN = ("artifacts" + "/", "reference" + "/")


def test_mcp_module_source_has_no_inner_folder_paths() -> None:
    module_dir = Path(__file__).resolve().parents[1]
    module_files = [
        p for p in sorted(module_dir.glob("*.py"))
    ]
    assert module_files, "no mcp module source files found"

    for path in module_files:
        content = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN:
            assert fragment not in content, f"{fragment!r} leaked into {path.name}"
