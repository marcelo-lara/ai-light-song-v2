from __future__ import annotations

import hashlib
import shutil
import urllib.request
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

DEMUCS_MODEL_NAME = "htdemucs"
DEMUCS_MODEL_SIGNATURE = "955717e8"
DEMUCS_MODEL_CHECKSUM = "8726e21a"
DEMUCS_MODEL_FILENAME = f"{DEMUCS_MODEL_SIGNATURE}-{DEMUCS_MODEL_CHECKSUM}.th"
DEMUCS_MODEL_URL = f"https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/{DEMUCS_MODEL_FILENAME}"
DEMUCS_MODEL_YAML = f"models: ['{DEMUCS_MODEL_SIGNATURE}']\n"


def _normalize_audio(audio):
    peak = float(abs(audio).max()) if audio.size else 0.0
    if peak <= 1e-8:
        return audio
    return audio / peak * 0.99


def _cleanup_legacy_demucs_directory(stems_dir: Path) -> None:
    legacy_directory = stems_dir / ".demucs"
    if legacy_directory.exists():
        shutil.rmtree(legacy_directory, ignore_errors=True)


def _demucs_repo_root() -> Path:
    return Path(__file__).resolve().parents[3] / "models" / "demucs"


def _checksum_prefix(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[: len(DEMUCS_MODEL_CHECKSUM)]


def _write_demucs_repo_manifest(repo_root: Path) -> None:
    manifest_path = repo_root / f"{DEMUCS_MODEL_NAME}.yaml"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") == DEMUCS_MODEL_YAML:
        return
    manifest_path.write_text(DEMUCS_MODEL_YAML, encoding="utf-8")


def _download_demucs_model(target_path: Path) -> None:
    temporary_path = target_path.with_suffix(target_path.suffix + ".tmp")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        with urllib.request.urlopen(DEMUCS_MODEL_URL) as response, temporary_path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        raise AnalysisError(f"Failed to download Demucs model checkpoint: {exc}") from exc
    checksum = _checksum_prefix(temporary_path)
    if checksum != DEMUCS_MODEL_CHECKSUM:
        temporary_path.unlink(missing_ok=True)
        raise AnalysisError(
            f"Downloaded Demucs model checksum mismatch: expected {DEMUCS_MODEL_CHECKSUM}, got {checksum}"
        )
    temporary_path.replace(target_path)


def _ensure_local_demucs_repo() -> Path:
    repo_root = _demucs_repo_root()
    ensure_directory(repo_root)
    _write_demucs_repo_manifest(repo_root)
    model_path = repo_root / DEMUCS_MODEL_FILENAME
    if model_path.exists() and _checksum_prefix(model_path) == DEMUCS_MODEL_CHECKSUM:
        return repo_root
    model_path.unlink(missing_ok=True)
    _download_demucs_model(model_path)
    return repo_root


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
        model_repo = _ensure_local_demucs_repo()
        model = get_model(DEMUCS_MODEL_NAME, repo=model_repo)
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
