"""v3.8 item 3 — `request_analysis` / `get_analysis_progress`.

Unit-level coverage of `runs.py` plus the two server tools that wrap it.
Every test works against a throwaway tmp analysis root and tmp songs root —
never the committed fixtures — so `test_fixtures_carry_no_inner_folders` in
test_server_tools.py keeps passing against the real fixture tree, and so
`test_exposure.py` (which only scans `mcp/*.py`, not `mcp/tests/`) is
unaffected by anything here.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = MCP_DIR / "tests" / "fixtures" / "analysis"


def _load(name: str, filename: str):
    sys.path.insert(0, str(MCP_DIR))
    spec = importlib.util.spec_from_file_location(name, MCP_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runs = _load("mcp_local_runs", "runs.py")
server = _load("mcp_local_server_runs", "server.py")


@pytest.fixture()
def writable_root(tmp_path, monkeypatch):
    root = tmp_path / "analysis"
    root.mkdir()
    shutil.copytree(FIXTURE_ROOT / "McpFull - Fixture", root / "McpFull - Fixture")
    monkeypatch.setenv("MCP_ANALYSIS_ROOT", str(root))
    return root


@pytest.fixture()
def songs_root(tmp_path, monkeypatch):
    root = tmp_path / "songs"
    root.mkdir()
    # Real (non-empty) audio — has_audio/list_unanalysed_audio_stems both
    # require size > 0, same as the real songs mount's actual audio files.
    (root / "McpUnanalysed - Fixture.mp3").write_bytes(b"stub-audio-bytes")
    monkeypatch.setenv("MCP_SONGS_ROOT", str(root))
    return root


def _request_path(root: Path, song: str) -> Path:
    return root / song / "artifacts" / "_run_request.json"


def _progress_path(root: Path, song: str) -> Path:
    return root / song / "artifacts" / "_run_progress.json"


# --- runs.py -----------------------------------------------------------


def test_get_songs_root_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("MCP_SONGS_ROOT", raising=False)
    assert runs.get_songs_root() == Path("/data/songs")
    monkeypatch.setenv("MCP_SONGS_ROOT", "/tmp/custom-songs")
    assert runs.get_songs_root() == Path("/tmp/custom-songs")


def test_has_audio_and_list_unanalysed_stems(songs_root) -> None:
    assert runs.has_audio("McpUnanalysed - Fixture", songs_root)
    assert not runs.has_audio("no-such-song", songs_root)
    assert runs.list_unanalysed_audio_stems(songs_root) == ["McpUnanalysed - Fixture"]


def test_list_unanalysed_audio_stems_missing_root_is_empty(tmp_path) -> None:
    assert runs.list_unanalysed_audio_stems(tmp_path / "does-not-exist") == []


# --- orchestrator review round 2: 0-byte placeholders / already-analysed ---


def test_has_audio_rejects_a_zero_byte_placeholder(tmp_path) -> None:
    (tmp_path / "authoring-drop1.mp3").write_bytes(b"")
    assert not runs.has_audio("authoring-drop1", tmp_path)


def test_has_audio_accepts_non_empty_file(tmp_path) -> None:
    (tmp_path / "Real - Song.mp3").write_bytes(b"x")
    assert runs.has_audio("Real - Song", tmp_path)


def test_has_audio_missing_file_is_false(tmp_path) -> None:
    assert not runs.has_audio("nothing-here", tmp_path)


def test_list_unanalysed_audio_stems_excludes_zero_byte_placeholders(tmp_path) -> None:
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    (songs_dir / "authoring-drop1.mp3").write_bytes(b"")
    (songs_dir / "authoring-drop2.mp3").write_bytes(b"")
    (songs_dir / "Real - Song.mp3").write_bytes(b"real audio bytes")
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()

    stems = runs.list_unanalysed_audio_stems(songs_dir, analysis_dir)
    assert stems == ["Real - Song"]


def test_list_unanalysed_audio_stems_excludes_already_analysed_songs(
    writable_root, tmp_path
) -> None:
    """`Cinderella - Ella Lee`-shaped case: a real, non-empty audio file
    whose song is already fully analysed must not appear as "unanalysed"."""
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    (songs_dir / "McpFull - Fixture.mp3").write_bytes(b"already analysed")
    (songs_dir / "McpUnanalysed - Fixture.mp3").write_bytes(b"not analysed yet")

    stems = runs.list_unanalysed_audio_stems(songs_dir, writable_root)
    assert stems == ["McpUnanalysed - Fixture"]


def test_request_analysis_refuses_a_zero_byte_audio_file(
    writable_root, tmp_path, monkeypatch
) -> None:
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    (songs_dir / "authoring-drop1.mp3").write_bytes(b"")
    monkeypatch.setenv("MCP_SONGS_ROOT", str(songs_dir))
    with pytest.raises(ToolError, match="No audio found"):
        server.request_analysis("authoring-drop1")


def test_write_request_creates_file_and_dirs(tmp_path) -> None:
    song_dir = tmp_path / "New - Song"
    payload = runs.write_request(song_dir, "New - Song")
    assert payload["song"] == "New - Song"
    assert payload["requested_at"].endswith("Z")
    on_disk = json.loads((song_dir / "artifacts" / "_run_request.json").read_text())
    assert on_disk == payload
    assert not (song_dir / "artifacts" / "_run_request.json.tmp").exists()


def test_read_request_and_progress_absent_return_none(tmp_path) -> None:
    song_dir = tmp_path / "Nothing - Here"
    assert runs.read_request(song_dir) is None
    assert runs.read_progress(song_dir) is None


def test_get_progress_or_derive_no_files_raises(tmp_path) -> None:
    with pytest.raises(runs.NoRunRequestedError, match="Nowhere - Song"):
        runs.get_progress_or_derive("Nowhere - Song", tmp_path / "Nowhere - Song")


def test_get_progress_or_derive_fresh_request_is_queued(tmp_path) -> None:
    song_dir = tmp_path / "Fresh - Song"
    runs.write_request(song_dir, "Fresh - Song")
    result = runs.get_progress_or_derive("Fresh - Song", song_dir)
    assert result["status"] == "queued"


def test_get_progress_or_derive_stale_request_is_not_started(tmp_path) -> None:
    song_dir = tmp_path / "Stale - Song"
    request_path = _request_path(tmp_path, "Stale - Song")
    request_path.parent.mkdir(parents=True)
    request_path.write_text(
        json.dumps({"song": "Stale - Song", "requested_at": "2000-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    result = runs.get_progress_or_derive("Stale - Song", song_dir)
    assert result["status"] == "not_started"
    assert "watcher" in result["note"]


def test_get_progress_or_derive_prefers_progress_file_verbatim(tmp_path) -> None:
    song_dir = tmp_path / "Running - Song"
    progress_path = _progress_path(tmp_path, "Running - Song")
    progress_path.parent.mkdir(parents=True)
    progress = {
        "song": "Running - Song", "status": "running", "stage": "segment-sections",
        "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
        "finished_at": None, "error": None,
    }
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    # Even with a request file also present, the progress file wins.
    runs.write_request(song_dir, "Running - Song")
    assert runs.get_progress_or_derive("Running - Song", song_dir) == progress


# --- server.request_analysis --------------------------------------------


def test_request_analysis_refuses_an_already_analysed_song(writable_root) -> None:
    with pytest.raises(ToolError, match="get_song_overview"):
        server.request_analysis("McpFull - Fixture")


def test_request_analysis_writes_a_request_for_a_new_song(writable_root, songs_root) -> None:
    result = server.request_analysis("McpUnanalysed - Fixture")
    assert result["status"] == "requested"
    assert result["poll_with"] == "get_analysis_progress"
    assert result["poll_every_s"] == 60
    assert _request_path(writable_root, "McpUnanalysed - Fixture").is_file()


def test_request_analysis_refuses_a_song_with_no_audio(writable_root, songs_root) -> None:
    with pytest.raises(ToolError, match="no-such-audio-xyz"):
        server.request_analysis("no-such-audio-xyz")
    assert not _request_path(writable_root, "no-such-audio-xyz").is_file()


def test_request_analysis_error_lists_unanalysed_stems(writable_root, songs_root) -> None:
    with pytest.raises(ToolError, match="McpUnanalysed - Fixture"):
        server.request_analysis("no-such-audio-xyz")


def test_request_analysis_returns_existing_progress_without_rewriting_request(
    writable_root, songs_root
) -> None:
    progress_path = _progress_path(writable_root, "McpUnanalysed - Fixture")
    progress_path.parent.mkdir(parents=True)
    progress = {
        "song": "McpUnanalysed - Fixture", "status": "running", "stage": "measure-loudness",
        "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
        "finished_at": None, "error": None,
    }
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    result = server.request_analysis("McpUnanalysed - Fixture")
    assert result.pop("watcher") in ("up", "down")
    assert result == progress
    assert not _request_path(writable_root, "McpUnanalysed - Fixture").exists()


def test_request_analysis_force_rewrites_request_for_an_analysed_song(
    writable_root, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("MCP_WATCHER_HEARTBEAT", str(tmp_path / "missing.heartbeat"))
    # Unforced stays a refusal, writes nothing.
    with pytest.raises(ToolError, match="force=True"):
        server.request_analysis("McpFull - Fixture")
    assert not _request_path(writable_root, "McpFull - Fixture").exists()
    # Forced writes the request. McpFull - Fixture has no audio in the
    # tmp songs root unless provided, so provide it.
    songs = tmp_path / "songs"
    songs.mkdir()
    (songs / "McpFull - Fixture.mp3").write_bytes(b"audio")
    monkeypatch.setenv("MCP_SONGS_ROOT", str(songs))
    result = server.request_analysis("McpFull - Fixture", force=True)
    assert result["status"] == "requested"
    assert result["watcher"] == "down"
    assert _request_path(writable_root, "McpFull - Fixture").is_file()


def test_request_analysis_force_still_needs_audio(writable_root, songs_root) -> None:
    with pytest.raises(ToolError, match="No audio found"):
        server.request_analysis("McpFull - Fixture", force=True)
    assert not _request_path(writable_root, "McpFull - Fixture").exists()


def test_request_analysis_reports_watcher_up_with_fresh_heartbeat(
    writable_root, songs_root, tmp_path, monkeypatch
) -> None:
    hb = tmp_path / "hb"
    hb.write_text(runs._now_iso_z() + "\n", encoding="utf-8")
    monkeypatch.setenv("MCP_WATCHER_HEARTBEAT", str(hb))
    result = server.request_analysis("McpUnanalysed - Fixture")
    assert result["watcher"] == "up"


# --- get_watcher_status ---------------------------------------------------


def _beat(path: Path, age_s: float) -> None:
    from datetime import datetime, timedelta, timezone

    when = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    path.write_text(when.strftime("%Y-%m-%dT%H:%M:%SZ") + "\n", encoding="utf-8")


def test_watcher_status_up_with_fresh_heartbeat(tmp_path, monkeypatch) -> None:
    hb = tmp_path / "hb"
    _beat(hb, 1)
    monkeypatch.setenv("MCP_WATCHER_HEARTBEAT", str(hb))
    monkeypatch.setenv("MCP_WATCHER_POLL_S", "2")
    status = server.get_watcher_status()
    assert status["status"] == "up"
    assert status["last_heartbeat"].endswith("Z")
    assert 0 <= status["age_s"] <= 4


def test_watcher_status_down_with_stale_heartbeat(tmp_path, monkeypatch) -> None:
    hb = tmp_path / "hb"
    _beat(hb, 60)
    monkeypatch.setenv("MCP_WATCHER_HEARTBEAT", str(hb))
    monkeypatch.setenv("MCP_WATCHER_POLL_S", "2")
    status = server.get_watcher_status()
    assert status["status"] == "down"
    assert status["age_s"] >= 59
    assert status["last_heartbeat"] is not None


def test_watcher_status_threshold_scales_with_poll_interval(tmp_path, monkeypatch) -> None:
    hb = tmp_path / "hb"
    _beat(hb, 20)
    monkeypatch.setenv("MCP_WATCHER_HEARTBEAT", str(hb))
    monkeypatch.setenv("MCP_WATCHER_POLL_S", "10")
    assert server.get_watcher_status()["status"] == "up"
    monkeypatch.setenv("MCP_WATCHER_POLL_S", "2")
    assert server.get_watcher_status()["status"] == "down"


def test_watcher_status_down_when_missing_or_garbage(tmp_path, monkeypatch) -> None:
    hb = tmp_path / "hb"
    monkeypatch.setenv("MCP_WATCHER_HEARTBEAT", str(hb))
    expected = {"status": "down", "last_heartbeat": None, "age_s": None}
    assert server.get_watcher_status() == expected
    hb.write_text("not a timestamp", encoding="utf-8")
    assert server.get_watcher_status() == expected


def test_watcher_status_default_path_is_beside_analysis_root(writable_root, monkeypatch) -> None:
    monkeypatch.delenv("MCP_WATCHER_HEARTBEAT", raising=False)
    assert runs.get_heartbeat_path() == writable_root.parent / "analysis-watcher.heartbeat"


# --- server.get_analysis_progress ----------------------------------------


def test_get_analysis_progress_errors_when_nothing_requested(writable_root) -> None:
    with pytest.raises(ToolError, match="request_analysis"):
        server.get_analysis_progress("Never - Requested")


def test_get_analysis_progress_reports_queued_right_after_request(
    writable_root, songs_root
) -> None:
    server.request_analysis("McpUnanalysed - Fixture")
    result = server.get_analysis_progress("McpUnanalysed - Fixture")
    assert result["status"] == "queued"


def test_get_analysis_progress_reports_not_started_for_a_stale_request(
    writable_root,
) -> None:
    request_path = _request_path(writable_root, "McpStale - Fixture")
    request_path.parent.mkdir(parents=True)
    request_path.write_text(
        json.dumps({"song": "McpStale - Fixture", "requested_at": "2000-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    result = server.get_analysis_progress("McpStale - Fixture")
    assert result["status"] == "not_started"


def test_get_analysis_progress_returns_progress_file_verbatim(writable_root) -> None:
    progress_path = _progress_path(writable_root, "McpFull - Fixture")
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress = {
        "song": "McpFull - Fixture", "status": "done", "stage": None,
        "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
        "finished_at": "2020-01-01T00:10:00Z", "error": None,
    }
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    assert server.get_analysis_progress("McpFull - Fixture") == progress


# --- orchestrator review fix 1: stale terminal progress vs a newer request --


def test_stale_failed_progress_is_ignored_when_a_newer_request_exists(tmp_path) -> None:
    """A run failed, then the caller called request_analysis again. The old
    `failed` progress must not be read back forever — get_progress_or_derive
    derives queued/not_started from the newer request instead."""
    song_dir = tmp_path / "Retry - Song"
    old_progress = {
        "song": "Retry - Song", "status": "failed", "stage": "measure-loudness",
        "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
        "finished_at": "2020-01-01T00:05:00Z", "error": "boom",
    }
    _progress_path(tmp_path, "Retry - Song").parent.mkdir(parents=True)
    _progress_path(tmp_path, "Retry - Song").write_text(json.dumps(old_progress), encoding="utf-8")
    # A fresh request, written after the failed run finished.
    runs.write_request(song_dir, "Retry - Song")

    result = runs.get_progress_or_derive("Retry - Song", song_dir)
    assert result["status"] == "queued"


def test_stale_failed_progress_with_stale_request_reports_not_started(tmp_path) -> None:
    """Same shape, but the newer request itself is now old (>120s) with no
    watcher having picked it up — the honest answer is not_started, never
    the old failed."""
    song_dir = tmp_path / "Retry2 - Song"
    old_progress = {
        "song": "Retry2 - Song", "status": "failed", "stage": None,
        "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
        "finished_at": "2020-01-01T00:05:00Z", "error": "boom",
    }
    _progress_path(tmp_path, "Retry2 - Song").parent.mkdir(parents=True)
    _progress_path(tmp_path, "Retry2 - Song").write_text(json.dumps(old_progress), encoding="utf-8")
    _request_path(tmp_path, "Retry2 - Song").write_text(
        json.dumps({"song": "Retry2 - Song", "requested_at": "2020-06-01T00:00:00Z"}),
        encoding="utf-8",
    )

    result = runs.get_progress_or_derive("Retry2 - Song", song_dir)
    assert result["status"] == "not_started"


def test_stale_done_progress_missing_finished_at_is_ignored(tmp_path) -> None:
    """A malformed/legacy progress row with no finished_at at all is treated
    as stale too (never read back verbatim) once a newer request exists."""
    song_dir = tmp_path / "Retry3 - Song"
    old_progress = {
        "song": "Retry3 - Song", "status": "done", "stage": None,
        "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
        "finished_at": None, "error": None,
    }
    _progress_path(tmp_path, "Retry3 - Song").parent.mkdir(parents=True)
    _progress_path(tmp_path, "Retry3 - Song").write_text(json.dumps(old_progress), encoding="utf-8")
    runs.write_request(song_dir, "Retry3 - Song")

    result = runs.get_progress_or_derive("Retry3 - Song", song_dir)
    assert result["status"] == "queued"


def test_running_progress_still_wins_over_a_newer_request(tmp_path) -> None:
    """A non-terminal progress (queued/running) is never treated as stale —
    a request arriving while a run is in flight legitimately queues a second
    job without touching the in-flight one's own progress."""
    song_dir = tmp_path / "InFlight - Song"
    running_progress = {
        "song": "InFlight - Song", "status": "running", "stage": "segment-sections",
        "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
        "finished_at": None, "error": None,
    }
    _progress_path(tmp_path, "InFlight - Song").parent.mkdir(parents=True)
    _progress_path(tmp_path, "InFlight - Song").write_text(
        json.dumps(running_progress), encoding="utf-8"
    )
    runs.write_request(song_dir, "InFlight - Song")

    result = runs.get_progress_or_derive("InFlight - Song", song_dir)
    assert result == running_progress


def test_terminal_progress_newer_than_request_still_wins(tmp_path) -> None:
    """A terminal progress whose finished_at is AFTER the request's
    requested_at (the ordinary case — the watcher picked up the request and
    finished the run) is returned verbatim, not treated as stale."""
    song_dir = tmp_path / "Finished - Song"
    _request_path(tmp_path, "Finished - Song").parent.mkdir(parents=True)
    _request_path(tmp_path, "Finished - Song").write_text(
        json.dumps({"song": "Finished - Song", "requested_at": "2020-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    done_progress = {
        "song": "Finished - Song", "status": "done", "stage": None,
        "requested_at": "2020-01-01T00:00:00Z", "started_at": "2020-01-01T00:00:05Z",
        "finished_at": "2020-01-01T00:10:00Z", "error": None,
    }
    _progress_path(tmp_path, "Finished - Song").write_text(
        json.dumps(done_progress), encoding="utf-8"
    )

    result = runs.get_progress_or_derive("Finished - Song", song_dir)
    assert result == done_progress


# --- orchestrator review fix 2: song-name validation ------------------------


@pytest.mark.parametrize(
    "bad_song",
    ["", "   ", "a/b", "a\\b", "..", "../etc", "foo/../bar", "..\\..\\x"],
)
def test_validate_song_name_rejects_unsafe_names(bad_song) -> None:
    with pytest.raises(runs.InvalidSongNameError):
        runs.validate_song_name(bad_song)


def test_validate_song_name_accepts_a_normal_name() -> None:
    assert runs.validate_song_name("McpFull - Fixture") == "McpFull - Fixture"
    assert runs.validate_song_name("  McpFull - Fixture  ") == "McpFull - Fixture"


@pytest.mark.parametrize("bad_song", ["../etc/passwd", "a/b", "a\\b", "..", ""])
def test_request_analysis_rejects_unsafe_song_names(writable_root, songs_root, bad_song) -> None:
    with pytest.raises(ToolError):
        server.request_analysis(bad_song)
    # Nothing escaped the analysis root: still exactly the one fixture dir.
    assert list(writable_root.iterdir()) == [writable_root / "McpFull - Fixture"]


@pytest.mark.parametrize("bad_song", ["../etc/passwd", "a/b", "a\\b", "..", ""])
def test_get_analysis_progress_rejects_unsafe_song_names(writable_root, bad_song) -> None:
    with pytest.raises(ToolError):
        server.get_analysis_progress(bad_song)


def test_request_analysis_with_traversal_name_writes_nothing_outside_root(
    writable_root, songs_root, tmp_path
) -> None:
    with pytest.raises(ToolError):
        server.request_analysis("../escaped")
    # The would-be escape target must not have been created.
    assert not (tmp_path / "escaped").exists()
