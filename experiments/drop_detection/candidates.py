"""Stage 1 (region proposal) + stage 3 (instant snap).

The measured failure of the v2.1 detector is that one weighted score modelled
one acoustic class of drop (bass re-entry). Across the seven gold impacts there
are at least three classes:

  * bass re-entry            `_test_song`, Titanium x3   bass +12..+38 dB
  * lead handover to a void  Armin x2                    vocals -39..-47 dB, mix DOWN
  * vocal hook entry         Hideaway                    vocals +24 dB, bass flat

What they share is not "energy rises" but "the lead role changes hands on a
beat". So stage 1 runs a bank of one-sided role-change channels and takes the
union of each channel's top peaks: recall first, precision is stage 2's job.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter

from .features import BAND_NAMES, HOP, SR, STEMS, SongFeatures

# Windows are (lo, hi) seconds relative to the candidate instant. They are wide
# because what separates a drop from a phrase boundary is that the new balance
# *holds*: a 1.6 s window mostly measures the vocal line's own gaps.
PRE_SHORT, POST_SHORT = (-4.3, -0.30), (0.30, 4.30)
PRE_LONG, POST_LONG = (-9.0, -0.30), (0.30, 9.00)

# Sidechain ducking makes a bass stem swing 20 dB within every bar. Levels are
# median-filtered to roughly a bar before any level is differenced, so a channel
# measures the arrangement rather than the pump.
SMOOTH_SECONDS = 1.5


def _smooth(x: np.ndarray, seconds: float = SMOOTH_SECONDS) -> np.ndarray:
    size = max(3, int(round(seconds * SR / HOP)) | 1)
    return median_filter(x, size=size, mode="nearest")


def _win(t: np.ndarray, x: np.ndarray, centre: float, lo: float, hi: float, fn=np.mean) -> float:
    mask = (t >= centre + lo) & (t < centre + hi)
    if not mask.any():
        return float("nan")
    return float(fn(x[mask]))


def _slope(t: np.ndarray, x: np.ndarray, centre: float, lo: float, hi: float) -> float:
    """dB per second of a least-squares fit over the window."""
    mask = (t >= centre + lo) & (t < centre + hi)
    if mask.sum() < 8:
        return 0.0
    tt, xx = t[mask], x[mask]
    return float(np.polyfit(tt - tt[0], xx, 1)[0])


def _clip01(x: float, hi: float, lo: float = 0.0) -> float:
    if not np.isfinite(x):
        return 0.0
    return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0))


def beat_table(feat: SongFeatures) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Per-beat descriptor of what changes across that beat."""
    t = feat.t
    stem_db = np.stack([_smooth(row) for row in feat.stem_db])
    band_db = np.stack([_smooth(row) for row in feat.band_db])
    mix_db = _smooth(feat.mix_db)
    flux_norm = max(1e-9, float(np.percentile(feat.flux, 99)))
    times = feat.beats[(feat.beats > 3.0) & (feat.beats < feat.duration - 2.0)]

    cols: dict[str, list[float]] = {}

    def put(name: str, value: float) -> None:
        cols.setdefault(name, []).append(value)

    for d in times:
        for i, stem in enumerate(STEMS):
            x = stem_db[i]
            put(f"d_{stem}_s", _win(t, x, d, *POST_SHORT) - _win(t, x, d, *PRE_SHORT))
            put(f"d_{stem}_l", _win(t, x, d, *POST_LONG) - _win(t, x, d, *PRE_LONG))
        for i, band in enumerate(BAND_NAMES):
            x = band_db[i]
            put(f"db_{band}_s", _win(t, x, d, *POST_SHORT) - _win(t, x, d, *PRE_SHORT))
        put("d_mix_s", _win(t, mix_db, d, *POST_SHORT) - _win(t, mix_db, d, *PRE_SHORT))
        put("d_mix_l", _win(t, mix_db, d, *POST_LONG) - _win(t, mix_db, d, *PRE_LONG))

        # Bass re-entry against a robust pre-floor (25th pct of the smoothed
        # level), not the raw minimum, which every sidechain trough would win.
        bass = stem_db[STEMS.index("bass")]
        floor = _win(t, bass, d, -9.0, -0.30, lambda v: np.percentile(v, 25))
        put("bass_reentry", _win(t, bass, d, *POST_SHORT) - floor)

        # riser / build evidence in the run-up
        put("air_slope", _slope(t, band_db[BAND_NAMES.index("air")], d, -8.0, -0.3))
        put("mix_slope", _slope(t, mix_db, d, -10.0, -0.5))
        # pre-impact suck-out: how far the mix dips in the last bar vs before it
        put("suck", _win(t, mix_db, d, -2.0, -0.05, np.min) - _win(t, mix_db, d, -6.0, -2.0))
        # transient right on the instant
        put("flux_pk", _win(t, feat.flux, d, -0.06, 0.30, np.max) / flux_norm)
        put("drum_pk", _win(t, feat.drum_flux, d, -0.06, 0.30, np.max)
            / max(1e-9, float(np.percentile(feat.drum_flux, 99))))
        put("pos", float(d) / max(1e-6, feat.duration))

    table = {k: np.asarray(v, dtype=float) for k, v in cols.items()}
    table = {k: np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0) for k, v in table.items()}
    return times, table


# Each channel is a one-sided reading of the same descriptor table. A drop only
# has to look like ONE of these to be proposed.
#
# Scores stay in raw dB and are deliberately NOT clipped at the top: an early
# version clipped each channel to [0, 1], which saturated whole regions of a
# song at exactly 1.0 and left the top-K selection to break ties by array order.
# Titanium's three impacts (bass +12..+38 dB) were all lost that way.
def channels(table: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    pos = lambda x: np.maximum(x, 0.0)
    # Transient gate: a drop lands on a hit. Keeps a floor so a channel with a
    # soft onset is attenuated rather than zeroed.
    trans = 0.4 + 0.6 * np.clip(table["flux_pk"], 0.0, 1.5)
    build = 0.6 + 0.4 * np.clip(table["mix_slope"] / 1.0, 0.0, 1.5)
    return {
        "bass_in": pos(table["bass_reentry"]) * trans,
        "sub_in": pos(table["db_sub_s"] + table["db_bass_s"]) * trans,
        "voc_out": pos(-table["d_vocals_s"]) * trans,
        "voc_in": pos(table["d_vocals_s"]) * trans,
        "drums_in": pos(table["d_drums_s"]) * trans,
        "drums_out": pos(-table["d_drums_s"]) * trans,
        "handover": pos(table["bass_reentry"]) * pos(-table["d_vocals_s"]) / 20.0 * trans,
        "after_build": pos(table["d_mix_s"]) * build * trans,
        "after_suck": pos(-table["suck"]) * trans,
    }


def nms_order(times: np.ndarray, score: np.ndarray, spacing: float) -> list[int]:
    """All peaks in descending score, thinned so no two are within `spacing`."""
    kept: list[int] = []
    for i in np.argsort(-score):
        if score[i] <= 0.0:
            break
        if all(abs(times[i] - times[j]) > spacing for j in kept):
            kept.append(int(i))
    return kept


def _nms_top(times: np.ndarray, score: np.ndarray, k: int, spacing: float) -> list[int]:
    kept: list[int] = []
    for i in np.argsort(-score):
        if score[i] <= 0.0:
            break
        if all(abs(times[i] - times[j]) > spacing for j in kept):
            kept.append(int(i))
        if len(kept) >= k:
            break
    return kept


def localize(feat: SongFeatures, centre: float, radius: float = 2.5,
             leading_edge: float = 1.0) -> float:
    """Stage 3. Given a proposed region, place the impact instant on a beat.

    Stage 1 scores use wide (+-4 s) windows so a sustained change of arrangement
    outranks a phrase gap; the price is that the score plateaus over several bars
    and its argmax sits 1-3 s from the transition. The instant is therefore
    chosen separately here, from short adjacent windows gated on the broadband
    transient.

    `leading_edge` < 1.0 accepts the earliest beat scoring within that fraction
    of the best, implementing v2.2 item 4's "snap to the leading edge, not the
    evidence peak". Measured on the gold set it makes things worse (0.85 ->
    9/21 within tolerance, vs 13/21 for the plain argmax), because during a
    build the change score is already within 15% of its eventual peak, so the
    rule walks backwards into the riser. Default is therefore the argmax.

    The grid searched is the beat grid, never the bar grid: the nearest beat to a
    human impact is within 0.23 s on all seven gold impacts, whereas the nearest
    essentia downbeat misses by up to 0.88 s on three of them.
    """
    t = feat.t
    beats = feat.beats[(feat.beats >= centre - radius) & (feat.beats <= centre + radius)]
    if len(beats) == 0:
        return float(feat.beats[int(np.argmin(np.abs(feat.beats - centre)))])

    flux_norm = max(1e-9, float(np.percentile(feat.flux, 99)))
    curves = [_smooth(row, 0.35) for row in feat.stem_db] + [_smooth(feat.mix_db, 0.35)]

    scores = []
    for b in beats:
        change = sum(abs(_win(t, x, b, 0.10, 1.40) - _win(t, x, b, -1.40, -0.10)) for x in curves)
        transient = _win(t, feat.flux, b, -0.08, 0.30, np.max) / flux_norm
        score = transient * (1.0 + change / 10.0)
        scores.append(score if np.isfinite(score) else 0.0)

    scores = np.asarray(scores)
    threshold = scores.max() * leading_edge
    return float(beats[int(np.argmax(scores >= threshold))])


def propose(feat: SongFeatures, *, per_channel: int = 3, spacing: float = 8.0) -> list[dict]:
    times, table = beat_table(feat)
    if len(times) == 0:
        return []
    chans = channels(table)
    picked: dict[int, set[str]] = {}
    for name, score in chans.items():
        for i in _nms_top(times, score, per_channel, spacing):
            picked.setdefault(i, set()).add(name)

    out = []
    for i, names in sorted(picked.items()):
        row = {k: float(v[i]) for k, v in table.items()}
        row.update({f"ch_{k}": float(v[i]) for k, v in chans.items()})
        out.append({
            "beat_time": float(times[i]),
            "time": localize(feat, float(times[i])),
            "channels": sorted(names),
            "features": row,
        })
    return out
