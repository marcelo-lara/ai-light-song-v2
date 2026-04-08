from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from analyzer.exceptions import UsageError


def derive_song_name(song_path: Path) -> str:
    if song_path.suffix.lower() != ".mp3":
        raise UsageError(f"Expected an .mp3 song input, got: {song_path}")
    return song_path.stem


@dataclass(slots=True)
class SongPaths:
    song_path: Path
    artifacts_root: Path
    reference_root: Path | None
    output_root: Path
    stems_root: Path

    @property
    def song_name(self) -> str:
        return derive_song_name(self.song_path)

    @property
    def song_artifacts_dir(self) -> Path:
        return self.artifacts_root / self.song_name

    @property
    def song_output_dir(self) -> Path:
        return self.output_root / self.song_name

    @property
    def stems_dir(self) -> Path:
        return self.stems_root / self.song_name

    def artifact(self, *parts: str) -> Path:
        return self.song_artifacts_dir.joinpath(*parts)

    def reference(self, *parts: str) -> Path | None:
        if self.reference_root is None:
            return None
        return self.reference_root.joinpath(self.song_name, *parts)
