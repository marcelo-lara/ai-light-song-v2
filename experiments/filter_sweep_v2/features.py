"""Half-beat log-frequency spectrogram features of the harmonic stem.

Audio -> power STFT (4096 / hop 512 at 32 kHz) -> 6 bins per octave from 100 Hz to 15.5 kHz,
averaged over each half-beat window of `beats.json` (window i = [beat, beat + 1/2 beat),
the last beat gets one median beat). Per window:

  peak_hz    strongest spectral peak: the bin standing highest above a 13-bin (two octave)
             running mean of the dB spectrum -- the resonant peak of a filter. Reported, but
             in a dense mix it jumps between chord tones, so it is NOT the sweep signal.
  sharpness  that peak's height over the running mean, dB (resonance Q proxy).
  hl_db      10 log10(energy above 2 kHz / energy below 500 Hz): the high/low ratio. A
             low-pass opening raises it by raising the numerator only.
  roll_hz    frequency below which 99 % of the energy sits (bin centre). A low-pass cutoff
             moving up moves it up.
  level_db   loudest bin, dB (silence gate).

Silent windows (level_db more than SILENCE_DB under the song's 95th percentile) are NaN.
"""
from __future__ import annotations

import numpy as np

SR = 32000
N_FFT = 4096
HOP = 512
F_LO, F_HI, BINS_PER_OCT = 100.0, 15500.0, 6
HL_HIGH_HZ, HL_LOW_HZ = 2000.0, 500.0
ROLL_FRAC = 0.99
PROM_BINS = 13
SILENCE_DB = 50.0


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
                row = {k: float("nan") for k in ("peak_hz", "sharpness", "hl_db", "roll_hz", "level_db")}
            row.update({"beat_index": i, "half": half, "start_s": float(a), "end_s": float(b)})
            rows.append(row)
    levels = np.array([r["level_db"] for r in rows])
    floor = np.nanpercentile(levels, 95) - SILENCE_DB
    for r in rows:
        if not r["level_db"] >= floor:
            for k in ("peak_hz", "sharpness", "hl_db", "roll_hz", "level_db"):
                r[k] = float("nan")
    return rows
