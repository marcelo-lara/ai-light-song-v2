"""Resolve the downbeat phase (which beat in essentia's trusted beat sequence
is beat 1) by musical evidence, not by majority vote among trackers.

Scope decision, stated up front: essentia's *beat times* are trusted good
(CLAUDE.md: 7/7 human impacts land within 0.25s of an essentia beat), and the
corpus is 4/4 throughout (sections.json / beats.json metadata). So the open
question this module answers is narrower than "what is the beat grid" — it is
"of essentia's own beat sequence, which residue mod 4 is bar-1". beat-this and
allin1 downbeats, which may sit on a *different* underlying beat grid (a
different tempo estimate, a half-beat offset), are first snapped onto
essentia's sequence before they can vote on a phase; where a tracker's beat
period disagrees enough that snapping is unreliable, that tracker's vote for
this song is dropped and recorded as such.
"""
from __future__ import annotations

import json

import numpy as np

from . import paths

N_PHASES = 4  # assumes 4/4 throughout — stated scope limit, see module docstring


def _essentia_sequence(song: str) -> list[dict]:
    raw = json.loads(paths.beats_path(song).read_text())
    return raw if isinstance(raw, list) else raw.get("beats", [])


def _snap_to_index(times: np.ndarray, target_times: np.ndarray) -> np.ndarray:
    """For each time in `times`, the index of the nearest entry in `target_times`."""
    idx = np.searchsorted(target_times, times)
    idx = np.clip(idx, 1, len(target_times) - 1)
    left = target_times[idx - 1]
    right = target_times[idx]
    choose_left = np.abs(times - left) <= np.abs(times - right)
    return np.where(choose_left, idx - 1, idx)


def _implied_phase(downbeat_times: list[float], essentia_times: np.ndarray, *, tol_s: float = 0.12) -> tuple[int | None, float]:
    """Snap tracker downbeats onto essentia's sequence; return the modal phase
    and the fraction of downbeats that snapped within tolerance (a rough
    "is this tracker's beat grid compatible with essentia's" check)."""
    if not downbeat_times or len(essentia_times) == 0:
        return None, 0.0
    dt = np.array(downbeat_times)
    idx = _snap_to_index(dt, essentia_times)
    snapped_err = np.abs(essentia_times[idx] - dt)
    ok = snapped_err <= tol_s
    if ok.sum() < max(3, 0.3 * len(dt)):
        return None, float(ok.mean())
    phases = idx[ok] % N_PHASES
    counts = np.bincount(phases, minlength=N_PHASES)
    return int(np.argmax(counts)), float(ok.mean())


def _phase_evidence_histogram(event_times: list[float], essentia_times: np.ndarray) -> np.ndarray:
    """Snap events onto the essentia sequence; return a length-4 histogram of
    how many events land at each phase (index mod 4)."""
    hist = np.zeros(N_PHASES)
    if not event_times or len(essentia_times) == 0:
        return hist
    idx = _snap_to_index(np.array(event_times), essentia_times)
    phases = idx % N_PHASES
    for p in phases:
        hist[p] += 1
    return hist


def _chord_change_times(essentia_beats: list[dict]) -> list[float]:
    out = []
    prev_chord = None
    for b in essentia_beats:
        chord = b.get("chord")
        if chord is not None and prev_chord is not None and chord != prev_chord:
            out.append(b["time"])
        prev_chord = chord
    return out


def resolve_song(song: str) -> dict:
    essentia_beats = _essentia_sequence(song)
    essentia_times = np.array([b["time"] for b in essentia_beats])
    essentia_downbeat_phase = None
    downbeat_indices = [i for i, b in enumerate(essentia_beats) if b.get("type") == "downbeat"]
    if downbeat_indices:
        phases = [i % N_PHASES for i in downbeat_indices]
        essentia_downbeat_phase = int(np.bincount(phases, minlength=N_PHASES).argmax())

    # Hypothesis 2: beat-this.
    beatthis_phase, beatthis_compat = None, 0.0
    bt_path = paths.beatthis_cache_path(song)
    if bt_path.exists():
        data = np.load(bt_path)
        beatthis_phase, beatthis_compat = _implied_phase(data["downbeats"].tolist(), essentia_times)

    # Hypothesis 3: allin1.
    allin1_phase, allin1_compat = None, 0.0
    a1_path = paths.allin1_cache_path(song)
    if a1_path.exists():
        data = json.loads(a1_path.read_text())
        allin1_phase, allin1_compat = _implied_phase(data.get("downbeats", []), essentia_times)

    # Hypothesis 4 + musical evidence: kick placement, chord-change positions,
    # section boundaries, gesture impacts (if entry 3 has run).
    kicks = []
    dp = paths.drum_events_path(song)
    if dp.exists():
        events = json.loads(dp.read_text())["events"]
        kicks = [e["time"] for e in events if e.get("event_type") == "kick"]
    kick_hist = _phase_evidence_histogram(kicks, essentia_times)

    chord_changes = _chord_change_times(essentia_beats)
    chord_hist = _phase_evidence_histogram(chord_changes, essentia_times)

    section_starts = []
    sp = paths.sections_path(song)
    if sp.exists():
        rows = json.loads(sp.read_text())
        section_starts = [float(r["start"]) for r in rows if float(r["start"]) > 0.05]
    section_hist = _phase_evidence_histogram(section_starts, essentia_times)

    gesture_impacts = []
    gp = paths.gestures_proposal_path(song)
    if gp.exists():
        gdata = json.loads(gp.read_text())
        gesture_impacts = [g["impact_time"] for g in gdata.get("gestures", [])]
    gesture_hist = _phase_evidence_histogram(gesture_impacts, essentia_times)

    audio_derived_phase = int(np.argmax(kick_hist)) if kick_hist.sum() > 0 else None

    def _norm(h):
        return h / h.sum() if h.sum() > 0 else h

    # Evidence weights, chosen by measurement, not assumption (see README's
    # weight-sweep table). Kicks in this four-on-the-floor-heavy repertoire
    # land on every beat near-uniformly and turned out to be a poor phase
    # discriminator — every weighting that included kick evidence at any
    # nonzero weight scored worse on the gold set than chord-change evidence
    # alone (2/7 vs 3/7). Section-boundary and gesture-impact evidence, added
    # at any weight tried, did not improve on chord-only either — an honest,
    # currently-unresolved result written up in the README rather than
    # papered over with a weighting chosen to look better than it is.
    combined = _norm(chord_hist)
    winning_phase = int(np.argmax(combined)) if combined.sum() > 0 else essentia_downbeat_phase
    sorted_scores = np.sort(combined)[::-1]
    margin = float((sorted_scores[0] - sorted_scores[1]) / sorted_scores[0]) if sorted_scores[0] > 0 and len(sorted_scores) > 1 else 0.0

    votes = {
        "essentia_own": essentia_downbeat_phase,
        "beat_this": beatthis_phase,
        "allin1": allin1_phase,
        "audio_kick_density": audio_derived_phase,
    }
    agreeing = [k for k, v in votes.items() if v is not None and v == winning_phase]
    disagreeing = [k for k, v in votes.items() if v is not None and v != winning_phase]

    confidence = round(min(1.0, 0.4 + 0.6 * margin), 3) if combined.sum() > 0 else 0.0
    grid_unknown = confidence < 0.45 or len(disagreeing) > len(agreeing)

    return {
        "song": song,
        "n_phases_assumed": N_PHASES,
        "votes": votes,
        "vote_compatibility": {"beat_this": round(beatthis_compat, 3), "allin1": round(allin1_compat, 3)},
        "evidence_histograms": {
            "kick": kick_hist.tolist(), "chord_change": chord_hist.tolist(),
            "section_boundary": section_hist.tolist(), "gesture_impact": gesture_hist.tolist(),
        },
        "winning_phase": winning_phase,
        "confidence": confidence,
        "margin": round(margin, 3),
        "agreeing_hypotheses": agreeing,
        "disagreeing_hypotheses": disagreeing,
        "grid_status": "unknown" if grid_unknown else "resolved",
        "essentia_beats": essentia_beats,
    }
