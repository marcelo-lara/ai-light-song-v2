"""Phase-1 stage `extract-harmonic-spectrum` (v3.12 item 32; ported from `experiments/filter_sweep_v2`, item 31).

Half-beat log-frequency spectrogram features of the harmonic stem, the measurement behind
the `light-changes` stage's per-bar filter-sweep slope and state. A fact, not a claim: no
confidence. Phase 3 never reads audio, so the audio work is done here and the slopes,
thresholds and states are computed by `light_changes.py` from this artifact.

Audio -> power STFT (4096 / hop 512 at 32 kHz) -> 6 bins per octave from 100 Hz to 15.5 kHz,
averaged over each half-beat window of the published `beats.json` (window i = [beat, beat + 1/2
beat), the last beat gets one median beat). Per window:

  peak_hz    strongest spectral peak (bin standing highest above a 13-bin running mean of the dB
             spectrum). Reported, but in a dense mix it jumps between chord tones, so it drives nothing.
  sharpness  that peak's height over the running mean, dB.
  hl_db      10 log10(energy above 2 kHz / energy below 500 Hz): a low-pass opening raises it.
  roll_hz    frequency below which 99 % of the energy sits (bin centre).
  level_db   loudest bin, dB (silence gate).

Silent windows (level_db more than SILENCE_DB under the song's 95th percentile) and windows
with no STFT frame are `null`. Writes `artifacts/harmonic_spectrum/half_beats.json`.
Deterministic: pure arithmetic on the stem and the grid.
"""
from __future__ import annotations

import math

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

SR = 32000
N_FFT = 4096
HOP = 512
F_LO, F_HI, BINS_PER_OCT = 100.0, 15500.0, 6
HL_HIGH_HZ, HL_LOW_HZ = 2000.0, 500.0
ROLL_FRAC = 0.99
PROM_BINS = 13
SILENCE_DB = 50.0
FEATURE_KEYS = ("peak_hz", "sharpness", "hl_db", "roll_hz", "level_db")


def log_edges() -> np.ndarray:
    n = int(np.floor(np.log2(F_HI / F_LO) * BINS_PER_OCT)) + 1
    e = F_LO * 2.0 ** (np.arange(n + 1) / BINS_PER_OCT)
    return e[e < F_HI]


def log_spectrogram(y: np.ndarray, sr: int = SR) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(frame times, log-bin power [bins, frames], bin centres Hz, edges)."""
    import librosa

    s = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP)) ** 2
    f = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    t = librosa.frames_to_time(np.arange(s.shape[1]), sr=sr, hop_length=HOP)
    edges = log_edges()
    b = np.array([s[(f >= lo) & (f < hi)].sum(axis=0) for lo, hi in zip(edges[:-1], edges[1:])])
    return t, b, np.sqrt(edges[:-1] * edges[1:]), edges


def window_features(power: np.ndarray, centres: np.ndarray) -> dict:
    """Features of one window from its mean power per log bin."""
    p = 10.0 * np.log10(power + 1e-12)
    base = np.convolve(np.pad(p, PROM_BINS // 2, mode="edge"), np.ones(PROM_BINS) / PROM_BINS, "valid")
    k = int(np.argmax(p - base))
    hi, lo = power[centres > HL_HIGH_HZ].sum(), power[centres < HL_LOW_HZ].sum()
    cs = np.cumsum(power) / power.sum()
    return {
        "peak_hz": float(centres[k]), "sharpness": float((p - base)[k]),
        "hl_db": float(10.0 * np.log10((hi + 1e-12) / (lo + 1e-12))),
        "roll_hz": float(centres[min(int(np.searchsorted(cs, ROLL_FRAC)), len(centres) - 1)]),
        "level_db": float(p.max()),
    }


def half_beat_rows(times: np.ndarray, power: np.ndarray, centres: np.ndarray, beat_times: np.ndarray) -> list[dict]:
    """One row per half-beat window; NaN features where silent or no frame falls inside."""
    beat_len = float(np.median(np.diff(beat_times)))
    ends = list(beat_times[1:]) + [beat_times[-1] + beat_len]
    rows: list[dict] = []
    for i, s in enumerate(beat_times):
        mid = (s + ends[i]) / 2.0
        for half, (a, b) in enumerate(((s, mid), (mid, ends[i]))):
            m = (times >= a) & (times < b)
            if m.any():
                row = window_features(power[:, m].mean(axis=1), centres)
            else:
                row = {k: float("nan") for k in FEATURE_KEYS}
            row.update({"beat_index": i, "half": half, "start_s": float(a), "end_s": float(b)})
            rows.append(row)
    levels = np.array([r["level_db"] for r in rows])
    floor = np.nanpercentile(levels, 95) - SILENCE_DB
    for r in rows:
        if not r["level_db"] >= floor:
            for k in FEATURE_KEYS:
                r[k] = float("nan")
    return rows


def _json_row(r: dict) -> dict:
    return {k: (None if isinstance(v, float) and math.isnan(v) else (round(v, 3) if isinstance(v, float) else v))
            for k, v in r.items()}


def extract_harmonic_spectrum(paths: SongPaths) -> dict:
    wav = paths.stems_dir / "harmonic.wav"
    if not wav.exists():
        raise DependencyError(f"harmonic stem missing: {wav} (run ensure-stems first)")
    if not paths.beats_output_path.exists():
        raise AnalysisError("extract-harmonic-spectrum requires the published beats.json (run build-ui-data first).")
    import librosa

    beats = read_json(paths.beats_output_path)["beats"]
    if len(beats) < 8:
        raise AnalysisError("fewer than 8 beats; cannot build half-beat windows")
    y, sr = librosa.load(str(wav), sr=SR, mono=True)
    beat_t = np.array([float(b["time"]) for b in beats])
    times, power, centres, _ = log_spectrogram(y, sr)
    rows = half_beat_rows(times, power, centres, beat_t)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "engine": "harmonic-stem log-frequency spectrogram (6 bins/octave, 100 Hz-15.5 kHz) per half beat: "
                      "high/low energy ratio (>2 kHz vs <500 Hz), 99 % rolloff, resonant peak",
            "inputs": ["artifacts/stems/harmonic.wav", "beats.json"],
            "params": {"sr": SR, "n_fft": N_FFT, "hop": HOP, "bins_per_octave": BINS_PER_OCT,
                       "silence_db": SILENCE_DB, "rolloff_frac": ROLL_FRAC},
        },
        "half_beats": [_json_row(r) for r in rows],
    }
    write_json(paths.artifact("harmonic_spectrum", "half_beats.json"), payload)
    return payload
