"""Runs Demucs stem separation for one variant, independent of
`src/analyzer/stages/stems.py` (never imported, never edited — that file stays
pinned to `htdemucs`). The `apply_model`/`AudioFile` call shape mirrors
`stems.py::ensure_stems` because that shape is what makes a Demucs run at
all, not because this module depends on it.

Only `htdemucs` has a pre-mirrored local checkpoint under `models/demucs/`
(the one `stems.py` downloads and pins). `htdemucs_ft` and `htdemucs_6s` have
no local mirror in this repo, so `get_model(name)` falls back to Demucs's own
HuggingFace-then-legacy-AWS fetch, which needs network access. If that fetch
stalls or fails, `separate()` raises — the caller (run.py) reports it as a
checkpoint-fetch failure, not a silent skip.
"""
from __future__ import annotations

from pathlib import Path

from . import paths

#: `htdemucs` / `htdemucs_ft` are 4-source; `htdemucs_6s` adds `guitar` and
#: `piano` (pulled out of `other`, per the refinement doc).
STEM_FILENAMES: dict[str, dict[str, str]] = {
    "htdemucs": {"bass": "bass.wav", "drums": "drums.wav", "other": "harmonic.wav", "vocals": "vocals.wav"},
    "htdemucs_ft": {"bass": "bass.wav", "drums": "drums.wav", "other": "harmonic.wav", "vocals": "vocals.wav"},
    "htdemucs_6s": {
        "bass": "bass.wav",
        "drums": "drums.wav",
        "other": "harmonic.wav",
        "vocals": "vocals.wav",
        "guitar": "guitar.wav",
        "piano": "piano.wav",
    },
}


def _normalize_audio(audio):
    peak = float(abs(audio).max()) if audio.size else 0.0
    if peak <= 1e-8:
        return audio
    return audio / peak * 0.99


def cached_stems(song: str, variant: str) -> dict[str, str] | None:
    stem_files = STEM_FILENAMES[variant]
    out_dir = paths.stems_dir(song, variant)
    cached = {name: out_dir / filename for name, filename in stem_files.items()}
    if all(p.exists() and p.stat().st_size > 0 for p in cached.values()):
        return {name: str(p) for name, p in cached.items()}
    return None


def separate(song: str, variant: str, force: bool = False) -> dict[str, str]:
    """Returns `{logical_stem_name: wav_path}` for `variant`, using the cache
    under `experiments/demucs_ablation/cache/<song>/<variant>/` unless
    `force`. Never writes under `data/analysis/`."""
    if variant not in paths.VARIANTS:
        raise ValueError(f"unknown Demucs variant {variant!r}, expected one of {paths.VARIANTS}")

    if not force:
        cached = cached_stems(song, variant)
        if cached is not None:
            return cached

    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model

    repo: Path | None = None
    if variant == "htdemucs":
        local_repo = paths.REPO_ROOT / "models" / "demucs"
        if local_repo.is_dir():
            repo = local_repo  # reuse the same offline mirror production uses

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = get_model(variant, repo=repo)
    song_path = paths.song_audio_path(song)
    mix = AudioFile(str(song_path)).read(
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
    separated = {name: separated_tensor[i] for i, name in enumerate(model.sources)}

    stem_files = STEM_FILENAMES[variant]
    out_dir = paths.stems_dir(song, variant)
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved: dict[str, str] = {}
    for source_name, filename in stem_files.items():
        stem_audio = separated.get(source_name)
        if stem_audio is None:
            raise RuntimeError(
                f"variant {variant!r} did not produce source {source_name!r} "
                f"(model.sources={list(model.sources)})"
            )
        arr = stem_audio.detach().cpu().numpy().T
        arr = _normalize_audio(arr)
        target = out_dir / filename
        sf.write(target, arr, model.samplerate, subtype="PCM_16")
        resolved[source_name] = str(target)
    return resolved
