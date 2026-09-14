"""Where this module reads and writes — reuses `analyzer.paths.SongPaths`
(the main pipeline's own convention for `data/analysis/{song}/...` paths)
rather than reinventing path logic. Promoted modules may import `src/`
(unlike `experiments/`, which never does)."""
from __future__ import annotations

from pathlib import Path

from analyzer.paths import SongPaths


def vocals_stem_path(paths: SongPaths) -> Path:
    return paths.stems_dir / "vocals.wav"


def output_path(paths: SongPaths) -> Path:
    return paths.artifact("whisperx-vad", "whisperx_vad.json")
