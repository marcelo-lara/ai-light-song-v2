"""`./analysis-watcher` (host script, run
via subprocess against a tmp data dir and a stub `docker`). Never touches
real `data/`."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import time
import unittest
from pathlib import Path

from analyzer.pipeline import STAGE_PIPELINE_IDS

REPO_ROOT = Path(__file__).resolve().parents[1]
WATCHER = REPO_ROOT / "analysis-watcher"

# A stub `docker` that understands only what the watcher issues:
#   <stub> compose run --rm -T app ./analyze --song <path> --stage ensure-stems --device cuda
#   <stub> compose run --rm -T whisperx --song <path>
#   <stub> compose run --rm -T app ./analyze --song <path> --device cuda
# A "step" is the service name, or "<service>_stage_<stage>" when a --stage
# flag is present (distinguishes the ensure-stems-only app invocation from
# the full analyze app invocation for the same song). Behaviour per
# (step, song) is driven by files under $STUB_CONFIG_DIR, named
# "<step>__<song>.<suffix>":
#   .out1            printed immediately
#   .block_sentinel  path to a file; the stub waits (polling) until it exists
#   .out2            printed after the block clears (or immediately, if none)
#   .exit            exit code (default 0)
# Every invocation also appends "<step> <song>" to $STUB_CALL_LOG (if set),
# in invocation order — tests use this to assert step ordering.
STUB_DOCKER = r"""#!/usr/bin/env bash
set -euo pipefail
shift 2  # drop "compose" "run"
service=""
song_path=""
stage=""
args=("$@")
i=0
n=${#args[@]}
while [[ $i -lt $n ]]; do
  a="${args[$i]}"
  case "$a" in
    --rm|-T) ;;
    --song)
      i=$((i+1))
      song_path="${args[$i]}"
      ;;
    --device)
      i=$((i+1))
      ;;
    --stage)
      i=$((i+1))
      stage="${args[$i]}"
      ;;
    ./analyze) ;;
    *)
      if [[ -z "$service" ]]; then service="$a"; fi
      ;;
  esac
  i=$((i+1))
done
song="$(basename "$song_path" .mp3)"
step="$service"
if [[ -n "$stage" ]]; then
  step="${service}_stage_${stage}"
fi
if [[ -n "${STUB_CALL_LOG:-}" ]]; then
  printf '%s %s\n' "$step" "$song" >> "$STUB_CALL_LOG"
fi
cfg="$STUB_CONFIG_DIR/${step}__${song}"
if [[ -f "${cfg}.pre" ]]; then
  bash "${cfg}.pre"
fi
if [[ -f "${cfg}.out1" ]]; then
  cat "${cfg}.out1"
fi
if [[ -f "${cfg}.block_sentinel" ]]; then
  sentinel="$(cat "${cfg}.block_sentinel")"
  until [[ -f "$sentinel" ]]; do sleep 0.05; done
fi
if [[ -f "${cfg}.out2" ]]; then
  cat "${cfg}.out2"
  # Give the watcher's poll loop a real window to observe the stage this
  # line just set before the process exits and the state flips to done.
  sleep 0.5
fi
exit_code=0
if [[ -f "${cfg}.exit" ]]; then
  exit_code="$(cat "${cfg}.exit")"
fi
exit "$exit_code"
"""


def _install_stub(bin_dir: Path) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "docker-stub"
    stub.write_text(STUB_DOCKER, encoding="utf-8")
    mode = stub.stat().st_mode
    stub.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def _configure(config_dir: Path, service: str, song: str, *, out1: str | None = None,
                out2: str | None = None, block_sentinel: Path | None = None,
                exit_code: int = 0, pre: str | None = None) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    prefix = config_dir / f"{service}__{song}"
    if pre is not None:
        prefix.with_name(prefix.name + ".pre").write_text(pre, encoding="utf-8")
    if out1 is not None:
        prefix.with_name(prefix.name + ".out1").write_text(out1, encoding="utf-8")
    if out2 is not None:
        prefix.with_name(prefix.name + ".out2").write_text(out2, encoding="utf-8")
    if block_sentinel is not None:
        prefix.with_name(prefix.name + ".block_sentinel").write_text(str(block_sentinel), encoding="utf-8")
    prefix.with_name(prefix.name + ".exit").write_text(str(exit_code), encoding="utf-8")


def _write_request(data_dir: Path, song: str) -> Path:
    artifacts_dir = data_dir / "analysis" / song / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    request_path = artifacts_dir / "_run_request.json"
    request_path.write_text(json.dumps({"song": song, "requested_at": "n/a"}), encoding="utf-8")
    return request_path


def _mark_whisperx_done(data_dir: Path, song: str) -> None:
    d = data_dir / "analysis" / song / "artifacts" / "whisperx-vad"
    d.mkdir(parents=True, exist_ok=True)
    (d / "whisperx_vad.json").write_text("{}", encoding="utf-8")


def _mark_stems_done(data_dir: Path, song: str) -> None:
    d = data_dir / "analysis" / song / "artifacts" / "stems"
    d.mkdir(parents=True, exist_ok=True)
    (d / "vocals.wav").write_bytes(b"")


def _progress_path(data_dir: Path, song: str) -> Path:
    return data_dir / "analysis" / song / "artifacts" / "_run_progress.json"


def _read_progress(data_dir: Path, song: str) -> dict | None:
    p = _progress_path(data_dir, song)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _wait_for(predicate, timeout: float = 10.0, interval: float = 0.05):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s (last value: {last!r})")


def _env(data_dir: Path, docker_stub: Path, config_dir: Path, poll_s: str = "0.2",
         call_log: Path | None = None) -> dict:
    env = dict(os.environ)
    env["ANALYSIS_WATCHER_DOCKER"] = str(docker_stub)
    env["ANALYSIS_WATCHER_DATA"] = str(data_dir)
    env["ANALYSIS_WATCHER_POLL_S"] = poll_s
    env["STUB_CONFIG_DIR"] = str(config_dir)
    if call_log is not None:
        env["STUB_CALL_LOG"] = str(call_log)
    return env


def _read_call_log(call_log: Path, song: str) -> list[str]:
    """Steps invoked for `song`, in invocation order (each line is
    "<step> <song>")."""
    if not call_log.exists():
        return []
    steps = []
    for raw_line in call_log.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        step, _, line_song = raw_line.rpartition(" ")
        if line_song == song:
            steps.append(step)
    return steps


class KnownStageListTests(unittest.TestCase):
    def test_script_stage_list_matches_pipeline(self) -> None:
        text = WATCHER.read_text(encoding="utf-8")
        start = text.index("KNOWN_STAGES=(")
        end = text.index(")", start)
        block = text[start:end]
        names = [line.strip().strip('"') for line in block.splitlines()[1:] if line.strip().startswith('"')]
        self.assertEqual(set(names), set(STAGE_PIPELINE_IDS.keys()))


class AnalysisWatcherTests(unittest.TestCase):
    def _make_dirs(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        (data_dir / "analysis").mkdir(parents=True)
        bin_dir = tmp_path / "bin"
        config_dir = tmp_path / "stub_config"
        docker_stub = _install_stub(bin_dir)
        return data_dir, docker_stub, config_dir

    def test_heartbeat_written_as_iso_timestamp(self) -> None:
        import re
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)
            result = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            beat = data_dir / "analysis-watcher.heartbeat"
            self.assertTrue(beat.is_file())
            self.assertRegex(
                beat.read_text(encoding="utf-8").strip(),
                r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
            )

    def test_done_and_failed_with_escaped_error(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)

            # --- done case ---
            song = "song_ok"
            _mark_whisperx_done(data_dir, song)
            _write_request(data_dir, song)
            _configure(config_dir, "app", song,
                       out1=f"[EPIC 1 | 1.1] {song} | ensure-stems\n"
                            f"[EPIC 3 | 3.1] {song} | segment-sections\n",
                       exit_code=0)

            result = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            progress = _read_progress(data_dir, song)
            self.assertIsNotNone(progress)
            self.assertEqual(progress["status"], "done")
            self.assertIsNone(progress["error"])
            self.assertIsNone(progress["stage"])
            self.assertIsNotNone(progress["finished_at"])
            self.assertFalse((data_dir / "analysis" / song / "artifacts" / "_run_request.json").exists())

            # --- failed case, with an error message that needs escaping and
            # truncation to the last 20 lines ---
            song2 = "song_bad"
            _mark_whisperx_done(data_dir, song2)
            _write_request(data_dir, song2)
            lines = [f'line {i} with "quotes" and a backslash \\' for i in range(25)]
            _configure(config_dir, "app", song2, out1="\n".join(lines) + "\n", exit_code=1)

            result2 = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result2.returncode, 0, result2.stderr)

            progress2 = _read_progress(data_dir, song2)
            self.assertIsNotNone(progress2)
            self.assertEqual(progress2["status"], "failed")
            self.assertIsNotNone(progress2["error"])
            # last 20 lines only -> line 5..24 survive, line 0..4 are dropped
            self.assertNotIn("line 4 ", progress2["error"])
            self.assertIn("line 24 ", progress2["error"])
            self.assertIn('"quotes"', progress2["error"])

    def test_whisperx_invoked_only_when_artifact_missing(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)

            # Case A: artifact missing -> whisperx must run before app.
            song_a = "song_needs_whisperx"
            called_marker = config_dir / "whisperx_called_a"
            artifact_path = data_dir / "analysis" / song_a / "artifacts" / "whisperx-vad" / "whisperx_vad.json"
            # The whisperx stub actually creates the artifact, like the real
            # service would, plus a marker file this test checks for the call.
            _configure(config_dir, "whisperx", song_a,
                       pre=f"mkdir -p '{artifact_path.parent}' && echo '{{}}' > '{artifact_path}' "
                           f"&& touch '{called_marker}'\n",
                       exit_code=0)
            _configure(config_dir, "app", song_a,
                       out1=f"[EPIC 1 | 1.1] {song_a} | ensure-stems\n", exit_code=0)
            _write_request(data_dir, song_a)

            result = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(called_marker.exists(), "whisperx stub was not invoked")
            progress_a = _read_progress(data_dir, song_a)
            self.assertEqual(progress_a["status"], "done")

            # Case B: artifact already present -> whisperx must NOT run.
            song_b = "song_has_whisperx"
            _mark_whisperx_done(data_dir, song_b)
            called_marker_b = config_dir / "whisperx_called_b"
            _configure(config_dir, "whisperx", song_b,
                       pre=f"touch '{called_marker_b}'\n", exit_code=0)
            _configure(config_dir, "app", song_b,
                       out1=f"[EPIC 1 | 1.1] {song_b} | ensure-stems\n", exit_code=0)
            _write_request(data_dir, song_b)

            result_b = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result_b.returncode, 0, result_b.stderr)
            self.assertFalse(called_marker_b.exists(), "whisperx stub ran despite an existing artifact")
            progress_b = _read_progress(data_dir, song_b)
            self.assertEqual(progress_b["status"], "done")

    def test_stale_running_progress_becomes_failed_on_startup(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)

            song = "song_interrupted"
            progress_path = _progress_path(data_dir, song)
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            progress_path.write_text(json.dumps({
                "song": song, "status": "running", "stage": "ensure-stems",
                "requested_at": "2026-01-01T00:00:00Z",
                "started_at": "2026-01-01T00:00:01Z",
                "finished_at": None, "error": None,
            }), encoding="utf-8")

            result = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            progress = _read_progress(data_dir, song)
            self.assertEqual(progress["status"], "failed")
            self.assertEqual(progress["error"], "interrupted: watcher restarted")

    def test_fifo_second_song_queued_while_first_runs_and_stage_tracks_markers(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)

            song_a = "song_first"
            song_b = "song_second"
            _mark_whisperx_done(data_dir, song_a)
            _mark_whisperx_done(data_dir, song_b)

            sentinel = tmp_path / "unblock_a"
            _configure(
                config_dir, "app", song_a,
                out1=f"[EPIC 1 | 1.1] {song_a} | ensure-stems\n",
                block_sentinel=sentinel,
                out2=f"[EPIC 3 | 3.1] {song_a} | segment-sections\n",
                exit_code=0,
            )
            _configure(
                config_dir, "app", song_b,
                out1=f"[EPIC 1 | 1.1] {song_b} | ensure-stems\n",
                exit_code=0,
            )

            req_a = _write_request(data_dir, song_a)
            time.sleep(0.05)  # ensure a's request mtime sorts before b's
            _write_request(data_dir, song_b)

            proc = subprocess.Popen(
                [str(WATCHER), "--foreground"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            try:
                # song_a picked up first (FIFO), stage reflects its first marker.
                _wait_for(lambda: (_read_progress(data_dir, song_a) or {}).get("stage") == "ensure-stems")
                self.assertFalse(req_a.exists(), "request file must be gone once running")

                # song_b is queued while song_a is still running.
                progress_b = _wait_for(lambda: _read_progress(data_dir, song_b))
                self.assertEqual(progress_b["status"], "queued")
                self.assertEqual((_read_progress(data_dir, song_a) or {}).get("status"), "running")

                sentinel.write_text("go", encoding="utf-8")

                # stage advances to the second marker, then the job completes.
                _wait_for(lambda: (_read_progress(data_dir, song_a) or {}).get("stage") == "segment-sections")
                _wait_for(lambda: (_read_progress(data_dir, song_a) or {}).get("status") == "done")

                # song_b then runs to completion (FIFO order respected).
                _wait_for(lambda: (_read_progress(data_dir, song_b) or {}).get("status") == "done")
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)

    def test_whisperx_failure_is_not_swallowed(self) -> None:
        """A failing whisperx run must mark the job `failed` and never invoke
        `./analyze` at all — regression for the `if ! cmd; then exit_code=$?`
        bug, where `$?` inside that branch is the status of the negation
        (always 0), not whisperx's real exit code, so a failing whisperx
        silently fell through to a full analyze run."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)

            song = "song_whisperx_fails"
            # whisperx artifact intentionally absent -> watcher must run it.
            _configure(config_dir, "whisperx", song,
                       out1="whisperx blew up\n", exit_code=3)

            app_called_marker = config_dir / "app_called"
            _configure(config_dir, "app", song,
                       pre=f"touch '{app_called_marker}'\n",
                       out1=f"[EPIC 1 | 1.1] {song} | ensure-stems\n", exit_code=0)

            _write_request(data_dir, song)

            result = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            progress = _read_progress(data_dir, song)
            self.assertIsNotNone(progress)
            self.assertEqual(progress["status"], "failed")
            self.assertIn("whisperx blew up", progress["error"])
            self.assertFalse(app_called_marker.exists(),
                              "./analyze must never run after a failing whisperx")

    def test_late_request_marked_queued_while_earlier_job_still_running(self) -> None:
        """A request that arrives *after* song A has already started running
        must be marked `queued` promptly — before A finishes — not only once
        the watcher gets around to the next sweep between jobs. Regression
        for `mark_all_queued` only running in `process_queue_once`'s
        between-job sweeps while `run_one_job` blocks for the whole (real:
        multi-minute) whisperx + analyze run. The MCP/UI both report a
        request as unwatched once it is >120s old with no progress file, so
        a slow-to-appear `queued` state is a false "not_started"/"no watcher
        running" report on any real run."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)

            song_a = "song_running_late_arrival"
            song_b = "song_arrives_during_run"
            _mark_whisperx_done(data_dir, song_a)
            _mark_whisperx_done(data_dir, song_b)

            sentinel = tmp_path / "unblock_a"
            _configure(
                config_dir, "app", song_a,
                out1=f"[EPIC 1 | 1.1] {song_a} | ensure-stems\n",
                block_sentinel=sentinel,
                out2=f"[EPIC 3 | 3.1] {song_a} | segment-sections\n",
                exit_code=0,
            )
            _configure(
                config_dir, "app", song_b,
                out1=f"[EPIC 1 | 1.1] {song_b} | ensure-stems\n",
                exit_code=0,
            )

            _write_request(data_dir, song_a)

            proc = subprocess.Popen(
                [str(WATCHER), "--foreground"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir, poll_s="0.2"),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            try:
                # Wait until song_a is confirmed running (blocked on its
                # sentinel) before song_b's request is even written.
                _wait_for(lambda: (_read_progress(data_dir, song_a) or {}).get("status") == "running")

                _write_request(data_dir, song_b)

                # song_b must flip to "queued" while song_a is still running
                # and blocked — i.e. well before the sentinel is released.
                _wait_for(lambda: (_read_progress(data_dir, song_b) or {}).get("status") == "queued",
                          timeout=5.0)
                self.assertEqual((_read_progress(data_dir, song_a) or {}).get("status"), "running",
                                  "song_a must still be running when song_b flips to queued")

                sentinel.write_text("go", encoding="utf-8")
                _wait_for(lambda: (_read_progress(data_dir, song_a) or {}).get("status") == "done")
                _wait_for(lambda: (_read_progress(data_dir, song_b) or {}).get("status") == "done")
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)

    def test_stems_missing_runs_ensure_stems_then_whisperx_then_analyze(self) -> None:
        """D1.1 corrected order (host end-to-end regression): whisperX reads
        the vocal stem, which only the analyzer's own `ensure-stems` stage
        produces, so on a never-analysed song the watcher must run
        `ensure-stems` alone first, then whisperX, then the full analyze —
        never whisperX before any stem exists."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)
            call_log = tmp_path / "call_log.txt"

            song = "song_never_analysed"
            # Neither artifacts/stems/vocals.wav nor whisperx_vad.json exists.
            _configure(config_dir, "app_stage_ensure-stems", song, exit_code=0)
            _configure(config_dir, "whisperx", song, exit_code=0)
            _configure(config_dir, "app", song,
                       out1=f"[EPIC 1 | 1.1] {song} | ensure-stems\n", exit_code=0)
            _write_request(data_dir, song)

            result = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir, call_log=call_log),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            self.assertEqual(_read_call_log(call_log, song),
                              ["app_stage_ensure-stems", "whisperx", "app"])
            progress = _read_progress(data_dir, song)
            self.assertEqual(progress["status"], "done")

    def test_stems_present_whisperx_missing_skips_ensure_stems(self) -> None:
        """When the vocal stem already exists (a partial prior run, or a
        song analysed before whisperX existed), `ensure-stems` must not be
        re-run — only whisperX, then the full analyze."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)
            call_log = tmp_path / "call_log.txt"

            song = "song_stems_already_exist"
            _mark_stems_done(data_dir, song)
            # whisperx_vad.json intentionally absent.
            _configure(config_dir, "whisperx", song, exit_code=0)
            _configure(config_dir, "app", song,
                       out1=f"[EPIC 1 | 1.1] {song} | ensure-stems\n", exit_code=0)
            _write_request(data_dir, song)

            result = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir, call_log=call_log),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            self.assertEqual(_read_call_log(call_log, song), ["whisperx", "app"])
            progress = _read_progress(data_dir, song)
            self.assertEqual(progress["status"], "done")

    def test_ensure_stems_failure_stops_before_whisperx_and_analyze(self) -> None:
        """A failing `ensure-stems` step must fail the job immediately —
        neither whisperX nor the full analyze may run afterwards."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir, docker_stub, config_dir = self._make_dirs(tmp_path)
            call_log = tmp_path / "call_log.txt"

            song = "song_ensure_stems_fails"
            _configure(config_dir, "app_stage_ensure-stems", song,
                       out1="ensure-stems blew up\n", exit_code=2)
            # If either of these ran, the call log would show it — no need
            # for output/marker files on them.
            _configure(config_dir, "whisperx", song, exit_code=0)
            _configure(config_dir, "app", song, exit_code=0)
            _write_request(data_dir, song)

            result = subprocess.run(
                [str(WATCHER), "--once"], cwd=REPO_ROOT,
                env=_env(data_dir, docker_stub, config_dir, call_log=call_log),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            self.assertEqual(_read_call_log(call_log, song), ["app_stage_ensure-stems"])
            progress = _read_progress(data_dir, song)
            self.assertEqual(progress["status"], "failed")
            self.assertIn("ensure-stems blew up", progress["error"])


if __name__ == "__main__":
    unittest.main()
