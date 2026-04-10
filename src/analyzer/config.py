from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from analyzer.exceptions import UsageError
from analyzer.paths import SongPaths


@dataclass(slots=True)
class ValidationConfig:
    compare_targets: tuple[str, ...]
    report_json: Path
    report_md: Path | None
    fail_on_mismatch: bool
    beat_tolerance_seconds: float
    tolerance_seconds: float
    chord_min_overlap: float
    device: str | None
    verbose: bool


def default_validation_report_paths(paths: SongPaths) -> tuple[Path, Path]:
    validation_dir = paths.song_artifacts_dir / "validation"
    return validation_dir / "phase_1_report.json", validation_dir / "phase_1_report.md"


def discover_song_files(artifacts_root: str, songs_root: str | None = None) -> list[Path]:
    root = resolve_songs_root(artifacts_root, songs_root)
    songs = sorted(path for path in root.iterdir() if path.is_file() and path.suffix.lower() == ".mp3")
    if not songs:
        raise UsageError(f"No .mp3 files found in songs directory: {root}")
    return songs


def build_song_paths(song: str, artifacts_root: str, reference_root: str | None) -> SongPaths:
    song_path = Path(song)
    if not song_path.exists():
        raise UsageError(f"Song file does not exist: {song_path}")

    artifacts_path = Path(artifacts_root)
    workspace_root = artifacts_path.parent
    output_root = workspace_root / "output"
    stems_root = workspace_root / "stems"
    reference_path = Path(reference_root) if reference_root else None
    return SongPaths(
        song_path=song_path,
        artifacts_root=artifacts_path,
        reference_root=reference_path,
        output_root=output_root,
        stems_root=stems_root,
    )


def resolve_songs_root(artifacts_root: str, songs_root: str | None = None) -> Path:
    root = Path(songs_root) if songs_root else Path(artifacts_root).parent / "songs"
    if not root.exists():
        raise UsageError(f"Songs directory does not exist: {root}")
    if not root.is_dir():
        raise UsageError(f"Songs path is not a directory: {root}")
    return root
