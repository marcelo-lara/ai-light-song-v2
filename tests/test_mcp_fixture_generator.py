"""`mcp/tests/fixtures/build_fixtures.py` reproduces every committed fixture.

The committed tree under `mcp/tests/fixtures/analysis/` is the truth; the
generator must match it byte-for-byte, so it can always be re-run in full.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "mcp" / "tests" / "fixtures"
COMMITTED = FIXTURE_DIR / "analysis"


def _load_generator():
    spec = importlib.util.spec_from_file_location("mcp_build_fixtures", FIXTURE_DIR / "build_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_files(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*.json"))}


class FixtureGeneratorTests(unittest.TestCase):
    def test_generator_output_matches_committed_fixtures_byte_for_byte(self) -> None:
        generator = _load_generator()
        with tempfile.TemporaryDirectory() as tmp:
            generator.main(Path(tmp))
            generated = _json_files(Path(tmp))
        committed = _json_files(COMMITTED)
        self.assertEqual(sorted(generated), sorted(committed), "file set differs")
        for name, content in committed.items():
            self.assertEqual(generated[name], content, f"{name} drifted from the generator")


if __name__ == "__main__":
    unittest.main()
