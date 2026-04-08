from __future__ import annotations

import shutil
from pathlib import Path

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import ensure_directory, write_json
from analyzer.models import GeneratedFrom, SCHEMA_VERSION
from analyzer.paths import SongPaths


REQUIRED_STEMS = {
    "bass": "bass.wav",
    "drums": "drums.wav",
    "other": "harmonic.wav",
    "vocals": "vocals.wav",
}


def _normalize_audio(audio):
    peak = float(abs(audio).max()) if audio.size else 0.0
    if peak <= 1e-8:
        return audio
    return audio / peak * 0.99


def _cleanup_legacy_demucs_directory(stems_dir: Path) -> None:
    legacy_directory = stems_dir / ".demucs"
    if legacy_directory.exists():
        shutil.rmtree(legacy_directory, ignore_errors=True)


def ensure_stems(paths: SongPaths, force: bool = False) -> dict[str, str]:
    ensure_directory(paths.stems_dir)
    cached = {name: paths.stems_dir / filename for name, filename in REQUIRED_STEMS.items()}
    harmonic_cache = {
        "bass": cached["bass"],
        "drums": cached["drums"],
        "harmonic": cached["other"],
        "vocals": cached["vocals"],
    }
    if not force and all(path.exists() and path.stat().st_size > 0 for path in harmonic_cache.values()):
        _cleanup_legacy_demucs_directory(paths.stems_dir)
        return {key: str(value) for key, value in harmonic_cache.items()}

    try:
        import soundfile as sf
        import torch
        from demucs.apply import apply_model
        from demucs.audio import AudioFile
        from demucs.pretrained import get_model
    except ImportError as exc:
        raise DependencyError("demucs is required for stem separation") from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        model = get_model("htdemucs")
        mix = AudioFile(str(paths.song_path)).read(
            streams=0,
            samplerate=model.samplerate,
            channels=model.audio_channels,
        )
        separated_tensor = apply_model(
            model,
            mix[None],
            device=device,
            shifts=1,
            split=True,
            overlap=0.25,
            progress=False,
            num_workers=0,
        )[0]
        separated = {
            source_name: separated_tensor[index]
            for index, source_name in enumerate(model.sources)
        }
    except Exception as exc:
        raise AnalysisError(f"Demucs separation failed: {exc}") from exc

    resolved_stems: dict[str, str] = {}
    for source_name, target_name in REQUIRED_STEMS.items():
        target_path = paths.stems_dir / target_name
        stem_audio = separated.get(source_name)
        if stem_audio is None:
            raise AnalysisError(f"Required stem missing from demucs output: {source_name}")
        stem_array = stem_audio.detach().cpu().numpy().T
        stem_array = _normalize_audio(stem_array)
        sf.write(target_path, stem_array, model.samplerate, subtype="PCM_16")
        logical_name = "harmonic" if source_name == "other" else source_name
        resolved_stems[logical_name] = str(target_path)

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            engine="demucs",
        ),
        "stems": resolved_stems,
    }
    write_json(paths.stems_dir / "metadata.json", metadata)
    _cleanup_legacy_demucs_directory(paths.stems_dir)
    return resolved_stems
