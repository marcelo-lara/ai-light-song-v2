from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from experiments import run_queue


def _write_queue(dir_path: Path, body: str) -> Path:
    p = dir_path / "queue.toml"
    p.write_text(body, encoding="utf-8")
    return p


class SubstitutionTests(unittest.TestCase):
    def test_placeholders_substituted_per_token(self) -> None:
        stages = run_queue.substitute(
            "python -m experiments.x.run compute --song {song_name} --dir {analysis_dir}",
            {"song_name": "Armin - Revolution", "analysis_dir": "/data/analysis/Armin - Revolution",
             "song_path": "/data/songs/Armin - Revolution.mp3"},
        )
        self.assertEqual(len(stages), 1)
        self.assertEqual(
            stages[0],
            ["python", "-m", "experiments.x.run", "compute", "--song",
             "Armin - Revolution", "--dir", "/data/analysis/Armin - Revolution"],
        )

    def test_double_ampersand_splits_stages(self) -> None:
        stages = run_queue.substitute("a --song {song_name} && b {song_path}",
                                      {"song_name": "s", "song_path": "/p.mp3"})
        self.assertEqual(stages, [["a", "--song", "s"], ["b", "/p.mp3"]])


class QueueFileTests(unittest.TestCase):
    def test_seeded_queue_parses_with_three_enabled_app_rows(self) -> None:
        rows = run_queue.load_queue()
        names = [r["name"] for r in rows]
        self.assertEqual(
            sorted(names),
            ["phrase_periodicity", "structural_vs_micro", "texture_novelty"],
        )
        for row in rows:
            self.assertTrue(row["enabled"])
            self.assertEqual(row["image"], "app")
            self.assertEqual(row["name"], row["name"].strip())

    def test_missing_queue_file_raises_queue_error(self) -> None:
        with self.assertRaises(run_queue.QueueError):
            run_queue.load_queue(Path("/nonexistent/queue.toml"))


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.song = self.root / "songs" / "_test_song.mp3"
        self.song.parent.mkdir(parents=True, exist_ok=True)
        self.song.write_text("", encoding="utf-8")
        self.analysis_root = self.root / "analysis"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, queue_body: str, extra_argv: list[str] | None = None) -> tuple[int, str]:
        queue_path = _write_queue(self.root, queue_body)
        argv = ["--song", str(self.song), "--analysis-root", str(self.analysis_root)]
        argv += extra_argv or []
        buf = io.StringIO()
        with patch.object(run_queue, "QUEUE_PATH", queue_path), redirect_stdout(buf):
            code = run_queue.main(argv)
        return code, buf.getvalue()

    def test_only_filters_rows(self) -> None:
        body = (
            '[[experiment]]\nname="a"\ncommand="true"\nimage="app"\nenabled=true\n'
            '[[experiment]]\nname="b"\ncommand="true"\nimage="app"\nenabled=true\n'
        )
        code, out = self._run(body, ["--only", "a"])
        self.assertEqual(code, 0)
        self.assertIn("a x _test_song", out)
        self.assertNotIn("b x _test_song", out)

    def test_failing_row_recorded_not_raised_partial_failure_exits_zero(self) -> None:
        body = (
            '[[experiment]]\nname="ok_row"\ncommand="true"\nimage="app"\nenabled=true\n'
            '[[experiment]]\nname="bad_row"\ncommand="false"\nimage="app"\nenabled=true\n'
        )
        code, out = self._run(body)
        self.assertEqual(code, 0)
        self.assertRegex(out, r"ok_row x _test_song\s+->\s+ok")
        self.assertRegex(out, r"bad_row x _test_song\s+->\s+failed\(1\)")
        self.assertIn("1 ok, 1 failed, 0 skipped", out)

    def test_total_failure_exits_non_zero(self) -> None:
        body = '[[experiment]]\nname="bad"\ncommand="false"\nimage="app"\nenabled=true\n'
        code, out = self._run(body)
        self.assertEqual(code, 1)
        self.assertRegex(out, r"bad x _test_song\s+->\s+failed\(1\)")

    def test_non_app_image_skipped_with_reason(self) -> None:
        body = '[[experiment]]\nname="x"\ncommand="true"\nimage="gpu"\nenabled=true\n'
        code, out = self._run(body)
        self.assertEqual(code, 0)
        self.assertIn("skipped(needs image gpu", out)

    def test_disabled_row_skipped(self) -> None:
        body = '[[experiment]]\nname="x"\ncommand="true"\nimage="app"\nenabled=false\n'
        code, out = self._run(body)
        self.assertEqual(code, 0)
        self.assertIn("skipped(disabled)", out)


if __name__ == "__main__":
    unittest.main()
