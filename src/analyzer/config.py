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
    tolerance_seconds: float
    chord_min_overlap: float
    device: str | None
    verbose: bool


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
