"""Shared per-hit spectral SHAPE features for the three drum-label accuracy
checks (`clap_events`, `kick_check`, `crash_check` — product-refinement v3.9
item 2 and its "`crash` over-fires" bug). Not an experiment itself: no queue
row, no UI lane, no README — a math module the three import.

**The rule this module exists to serve:** never trust omnizart's
`event_type` label. Classify every hit by what its own spectrum looks like.
A loudness/onset gate alone is known to fail (misses soft claps, passes
loud machine hits that aren't claps) — see each caller's README for the
measured counter-examples. This module only computes features; each caller
owns its own verdict thresholds.

## Bands

Energy share = that band's FFT power / total power in the analysis window
(Hann-windowed real FFT, DC bin excluded from the denominator):

- `NOISE_BAND_HZ = (1000, 6000)` — the refinement's own "1-6 kHz noise
  share": what separates a clap/bright-hat/crash's broadband hiss from a
  tonal hit.
- `BODY_BAND_HZ = (120, 400)` — "120-400 Hz body": a clap or snare's
  low-mid resonance; near-zero for a clean noise burst, present in a kick,
  bass-heavy machine hit, or backbeat kick doubling as a false clap.
- `LOW_BAND_HZ = (20, 150)` — kick/sub register, `kick_check`'s "sub/low
  body".
- `BRIGHT_BAND_HZ = (2000, 16000)` — crash-cymbal brilliance register,
  `crash_check`'s decay-envelope band (the same register the v3.4
  crash/hat split gates on).

## Window length — measured, not assumed

`WIN_S = 0.12` (120 ms) reproduces the refinement's own worked numbers on
`Queen of Kings - Alessandra` (verified against the shipped `drums.wav` +
`beats.json`, see `experiments/clap_events/README.md`):

| hit | spec noise/body | this module at 120 ms |
| --- | --- | --- |
| break claps (bars 42-48 beat 3, 7 hits) | 0.56-0.92 / <=0.12 | 0.65-0.84 / <=0.12 |
| rejected machine hit, 97.309 s | 0.10 / 0.28 | 0.100 / 0.112 |
| drop-1 beat-3 backbeat | ~0 / 0.25 | 0.00-0.02 / 0.10-0.41 |

Shorter windows (20-40 ms) do not reproduce this: the machine hit's low
noise share only emerges once the window is long enough to average across
the initial transient and its immediate decay, and shorter windows read the
backbeat's body share as near-zero (its low end has not developed yet by
20 ms). Longer windows (>=200 ms) start pulling in the *next* hit at
typical corpus tempi and blur the shares upward. 120 ms was kept as the one
window used everywhere in this module — a different window per caller would
make the shared feature code meaningless to share.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"

NOISE_BAND_HZ = (1000.0, 6000.0)
BODY_BAND_HZ = (120.0, 400.0)
LOW_BAND_HZ = (20.0, 150.0)
BRIGHT_BAND_HZ = (2000.0, 16000.0)

WIN_S = 0.12  # 120 ms — see module docstring for the measurement.


def drums_stem_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / "drums.wav"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def drum_events_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "drum_events.json"


def all_songs() -> list[str]:
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and drums_stem_path(p.name).exists()
    )


@dataclass(frozen=True)
class DrumsStem:
    song: str
    y: np.ndarray  # mono float64
    sr: int

    @property
    def duration(self) -> float:
        return len(self.y) / self.sr


def load_drums_stem(song: str) -> DrumsStem:
    y, sr = sf.read(str(drums_stem_path(song)), always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    return DrumsStem(song=song, y=np.asarray(y, dtype=np.float64), sr=sr)


def load_beat_length(song: str) -> float:
    """Median beat-to-beat interval across the whole song. The corpus is 4/4
    at near-constant BPM by assumption (CLAUDE.md) so one song-wide median is
    the grid every per-hit check normalises against — never an absolute
    seconds constant, which would not transfer between songs of different
    tempo."""
    beats = json.loads(beats_path(song).read_text())["beats"]
    times = sorted(b["time"] for b in beats)
    diffs = np.diff(times)
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        raise ValueError(f"{song!r}: beats.json has fewer than 2 beats — cannot measure a beat length")
    return float(np.median(diffs))


def _band_share(power: np.ndarray, freqs: np.ndarray, total: float, lo: float, hi: float) -> float:
    mask = (freqs >= lo) & (freqs < hi)
    return float(power[mask].sum() / total)


@dataclass(frozen=True)
class HitShape:
    time: float
    noise_share: float  # NOISE_BAND_HZ fraction
    body_share: float  # BODY_BAND_HZ fraction
    low_share: float  # LOW_BAND_HZ fraction
    bright_share: float  # BRIGHT_BAND_HZ fraction


def hit_shape(stem: DrumsStem, time: float, win_s: float = WIN_S) -> HitShape | None:
    """The four band shares of the `win_s` window starting at `time`
    (the hit's onset, never centred — a hit's identity is in its attack).
    `None` when the window runs past the end of the stem (a hit within the
    last `win_s` of the song — rare, always at export time honoured as "no
    verdict" rather than a truncated, misleading share)."""
    n0 = int(round(time * stem.sr))
    n1 = int(round((time + win_s) * stem.sr))
    if n1 > len(stem.y) or n0 < 0:
        return None
    seg = stem.y[n0:n1]
    if len(seg) < 8:
        return None
    window = np.hanning(len(seg))
    spectrum = np.fft.rfft(seg * window)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(len(seg), 1.0 / stem.sr)
    total = float(power[1:].sum()) + 1e-12  # exclude DC
    return HitShape(
        time=time,
        noise_share=round(_band_share(power, freqs, total, *NOISE_BAND_HZ), 4),
        body_share=round(_band_share(power, freqs, total, *BODY_BAND_HZ), 4),
        low_share=round(_band_share(power, freqs, total, *LOW_BAND_HZ), 4),
        bright_share=round(_band_share(power, freqs, total, *BRIGHT_BAND_HZ), 4),
    )


def low_band_attack_strength(stem: DrumsStem, time: float, *, lowpass_hz: float = 200.0,
                              hop: int = 256) -> float:
    """Percussive-attack strength in the kick's own register — the spectral
    flux (librosa `onset_strength`) of a `lowpass_hz`-low-passed copy of the
    stem, read at `time`. Distinguishes a genuine kick transient from a
    sustained sub-bass pad that happens to share the kick's low_share: in
    `kick_check`'s measurement (`experiments/kick_check/README.md`), real
    drop kicks on `Rapture - Nadia Ali` score attack ratios of 17-150x a
    quiet pre-onset baseline; the Breakdown's mislabelled "kicks" (a
    sustained pad, no drums) score 0.8-3.0x — no attack at all. Read once per
    call and cached would be faster; kept simple since this module's callers
    each run it once per song via `attack_envelope`, not per hit."""
    return float(attack_envelope(stem, lowpass_hz=lowpass_hz, hop=hop).at(time))


@dataclass(frozen=True)
class AttackEnvelope:
    """Precomputed low-passed onset-strength envelope for one song, so a
    caller scoring hundreds of hits pays the STFT cost once."""
    values: np.ndarray
    hop: int
    sr: int

    def at(self, time: float) -> float:
        idx = int(round(time * self.sr / self.hop))
        idx = min(max(idx, 0), len(self.values) - 1)
        lo, hi = max(0, idx - 2), min(len(self.values), idx + 3)
        return float(self.values[lo:hi].max()) if hi > lo else float(self.values[idx])

    def percentile(self, pct: float) -> float:
        return float(np.percentile(self.values, pct))


def attack_envelope(stem: DrumsStem, *, lowpass_hz: float = 200.0, hop: int = 256) -> AttackEnvelope:
    import librosa
    from scipy.signal import butter, sosfiltfilt

    sos = butter(4, lowpass_hz, btype="lowpass", fs=stem.sr, output="sos")
    y_low = sosfiltfilt(sos, stem.y)
    env = librosa.onset.onset_strength(y=y_low, sr=stem.sr, hop_length=hop)
    return AttackEnvelope(values=env, hop=hop, sr=stem.sr)


def bright_decay_ratio(stem: DrumsStem, time: float, *, win_s: float = 0.4,
                        hop_s: float = 0.01) -> float | None:
    """How much of the peak brilliance-band (`BRIGHT_BAND_HZ`) energy is
    still present at the end of a `win_s` window after onset, as a fraction
    of the window's own peak. A genuine isolated crash rings and then goes
    quiet: `crash_check`'s measurement finds ratio ~0.02-0.03 for the
    accepted isolated hits. A hit sitting inside a busy hi-hat/ride stream
    never goes quiet — the next hit in the stream keeps the envelope up —
    measured at ~0.6 for a rejected stream member. `None` when the window
    runs past the end of the stem."""
    from scipy.signal import butter, sosfiltfilt

    n0 = int(round((time - hop_s) * stem.sr))
    n1 = int(round((time + win_s) * stem.sr))
    if n0 < 0 or n1 > len(stem.y):
        return None
    seg = stem.y[n0:n1]
    sos = butter(4, list(BRIGHT_BAND_HZ), btype="bandpass", fs=stem.sr, output="sos")
    seg_f = sosfiltfilt(sos, seg)
    hop_n = int(round(hop_s * stem.sr))
    if hop_n <= 0 or len(seg_f) < hop_n * 3:
        return None
    frames = [
        float(np.sqrt(np.mean(seg_f[i:i + hop_n] ** 2)))
        for i in range(0, len(seg_f) - hop_n, hop_n)
    ]
    envs = np.array(frames)
    peak = float(envs.max())
    if peak <= 1e-9:
        return None
    tail = float(envs[-1])
    return round(tail / peak, 4)


def is_stream_continuation(prev_time: float | None, time: float, beat_len: float,
                            *, tol_frac: float = 0.15) -> bool:
    """True if `time` is spaced from `prev_time` by ~1 or ~2 beats (within
    `tol_frac` of `beat_len`) — the refinement's "recur at a steady ~1-2 beat
    period" definition of a regular stream. Deliberately memoryless (looks
    at one preceding gap, not a run history): a run's first hit always has
    either no preceding hit in range or a preceding gap that breaks the
    pattern, so it never triggers this on its own — every hit *after* it
    that keeps matching does. See `crash_check/README.md` for why this
    reproduces `Cinderella - Ella Lee`'s "222.37 kept as one accent, the
    rest of that run rejected" case without a run-length special case."""
    if prev_time is None:
        return False
    gap = time - prev_time
    for n in (1, 2):
        target = n * beat_len
        if abs(gap - target) <= tol_frac * beat_len:
            return True
    return False
