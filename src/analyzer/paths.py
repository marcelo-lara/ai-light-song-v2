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
    analysis_root: Path

    @property
    def song_name(self) -> str:
        return derive_song_name(self.song_path)

    @property
    def song_output_dir(self) -> Path:
        return self.analysis_root / self.song_name

    @property
    def song_artifacts_dir(self) -> Path:
        return self.song_output_dir / "artifacts"

    @property
    def song_reference_dir(self) -> Path:
        return self.song_output_dir / "reference"

    @property
    def song_validation_dir(self) -> Path:
        return self.song_artifacts_dir / "validation"

    @property
    def stems_dir(self) -> Path:
        return self.song_artifacts_dir / "stems"

    @property
    def beats_output_path(self) -> Path:
        return self.song_output_dir / "beats.json"

    @property
    def hints_output_path(self) -> Path:
        return self.song_output_dir / "hints.json"

    @property
    def info_output_path(self) -> Path:
        return self.song_output_dir / "info.json"

    @property
    def sections_output_path(self) -> Path:
        return self.song_output_dir / "sections.json"

    @property
    def timeline_output_path(self) -> Path:
        return self.song_output_dir / "song_event_timeline.json"

    @property
    def lighting_score_output_path(self) -> Path:
        return self.song_output_dir / "lighting_score.md"

    @property
    def beatdrop_visual_plan_output_path(self) -> Path:
        return self.song_output_dir / "beatdrop_visual_plan.json"

    @property
    def beatdrop_visual_plan_md_output_path(self) -> Path:
        return self.song_output_dir / "beatdrop_visual_plan.md"

    @property
    def review_json_path(self) -> Path:
        return self.song_validation_dir / "song_events.review.json"

    @property
    def review_md_path(self) -> Path:
        return self.song_validation_dir / "song_events.review.md"

    @property
    def overrides_path(self) -> Path:
        return self.song_validation_dir / "song_events.overrides.json"

    @property
    def timeline_md_path(self) -> Path:
        return self.song_validation_dir / "song_event_timeline.md"

    def artifact(self, *parts: str) -> Path:
        return self.song_artifacts_dir.joinpath(*parts)

    def reference(self, *parts: str) -> Path:
        return self.song_reference_dir.joinpath(*parts)
