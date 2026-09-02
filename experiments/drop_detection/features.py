"""Frame-level feature cache built from the demucs stems + the essentia beat grid.

One `.npz` per song. Everything downstream reads this, so a full experiment
sweep over the corpus costs one decode pass, not one per idea.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .paths import beats_path, cache_path, stem_path

SR = 22050
HOP = 256                      # 11.6 ms
N_FFT = 2048
STEMS = ("bass", "drums", "harmonic", "vocals")
BANDS = ((20, 80), (80, 160), (160, 400), (400, 1200), (1200, 4000), (4000, 11000))
BAND_NAMES = ("sub", "bass", "low_mid", "mid", "high_mid", "air")
EPS_RMS = 1e-9
EPS_BAND = 1e-6


@dataclass
class SongFeatures:
    song: str
    t: np.ndarray            # (L,) frame times
    stem_db: np.ndarray      # (4, L) per-stem RMS in dB
    band_db: np.ndarray      # (6, L) mix band energy in dB
    mix_db: np.ndarray       # (L,)
    flux: np.ndarray         # (L,) mix onset strength
    drum_flux: np.ndarray    # (L,) drums-stem onset strength
    beats: np.ndarray        # (B,) essentia beat times
    downbeats: np.ndarray    # (D,)
    duration: float

    def stem(self, name: str) -> np.ndarray:
        return self.stem_db[STEMS.index(name)]

    def band(self, name: str) -> np.ndarray:
        return self.band_db[BAND_NAMES.index(name)]


def _db(x: np.ndarray, eps: float) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(x, eps))


def build(song: str) -> SongFeatures:
    import librosa

    waves = {}
    for stem in STEMS:
        wave, _ = librosa.load(str(stem_path(song, stem)), sr=SR, mono=True)
        waves[stem] = wave
    n = min(len(w) for w in waves.values())
    waves = {k: v[:n] for k, v in waves.items()}
    mix = sum(waves.values())

    def rms(wave):
        return librosa.feature.rms(y=wave, frame_length=1024, hop_length=HOP)[0]

    stem_rms = np.stack([rms(waves[s]) for s in STEMS])
    spec = np.abs(librosa.stft(mix, n_fft=N_FFT, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=SR, n_fft=N_FFT)
    band = np.stack([spec[(freqs >= lo) & (freqs < hi)].sum(0) for lo, hi in BANDS])
    flux = librosa.onset.onset_strength(S=librosa.power_to_db(spec ** 2), sr=SR, hop_length=HOP)
    drum_flux = librosa.onset.onset_strength(y=waves["drums"], sr=SR, hop_length=HOP)
    mix_rms = rms(mix)

    length = min(stem_rms.shape[1], band.shape[1], len(flux), len(drum_flux), len(mix_rms))
    beats_payload = json.loads(beats_path(song).read_text())
    beats = np.array([float(b["time"]) for b in beats_payload["beats"]])
    downbeats = np.array([float(b["time"]) for b in beats_payload["beats"] if b.get("type") == "downbeat"])

    return SongFeatures(
        song=song,
        t=librosa.frames_to_time(np.arange(length), sr=SR, hop_length=HOP),
        stem_db=_db(stem_rms[:, :length], EPS_RMS),
        band_db=_db(band[:, :length], EPS_BAND),
        mix_db=_db(mix_rms[:length], EPS_RMS),
        flux=flux[:length],
        drum_flux=drum_flux[:length],
        beats=beats,
        downbeats=downbeats,
        duration=float(n) / SR,
    )


def save(feat: SongFeatures) -> None:
    path = cache_path(feat.song)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        song=feat.song, t=feat.t, stem_db=feat.stem_db, band_db=feat.band_db,
        mix_db=feat.mix_db, flux=feat.flux, drum_flux=feat.drum_flux,
        beats=feat.beats, downbeats=feat.downbeats, duration=feat.duration,
    )


def load(song: str, *, rebuild: bool = False) -> SongFeatures:
    path = cache_path(song)
    if rebuild or not path.exists():
        feat = build(song)
        save(feat)
        return feat
    data = np.load(path, allow_pickle=False)
    return SongFeatures(
        song=song, t=data["t"], stem_db=data["stem_db"], band_db=data["band_db"],
        mix_db=data["mix_db"], flux=data["flux"], drum_flux=data["drum_flux"],
        beats=data["beats"], downbeats=data["downbeats"], duration=float(data["duration"]),
    )
