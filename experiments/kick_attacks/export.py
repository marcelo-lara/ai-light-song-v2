"""Compute (audio -> cache) and export (`reference/proposals/kick_attacks.json`).

`events[]`: `time` (physical onset, s), `confidence` (kick-attack confidence, off-grid
survivors x0.4, echoes capped at 0.2), `echo_of` (parent attack time, or null for a kick),
plus evidence `on_grid` / `grid` / `rise_db` / `click_db` / `pitch_drop`.
"""
from __future__ import annotations

import datetime
import json

import librosa
import numpy as np

from . import detect, paths

SCHEMA_VERSION = "1.0"


def compute(song: str) -> dict:
    audio = paths.mix_audio_path(song)
    if not audio.exists():
        raise FileNotFoundError(f"mix audio missing: {audio}")
    y, sr = librosa.load(str(audio), sr=detect.SR, mono=True)
    beats = json.loads(paths.beats_path(song).read_text())
    times = np.array(sorted(b["time"] for b in beats["beats"]), dtype=float)
    beat_len = float(np.median(np.diff(times)))
    off = [(s["start"], s["end"]) for s in beats.get("off_grid_spans", [])]
    payload = {"song": song, "beat_len": round(beat_len, 4), "events": detect.detect(y, sr, times, beat_len, off)}
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload) + "\n")
    return payload


def load_cache(song: str) -> dict:
    p = paths.cache_path(song)
    if not p.exists():
        raise FileNotFoundError(f"no cache for {song!r} — run `run compute --song {song!r}` first")
    return json.loads(p.read_text())


def export(song: str) -> dict:
    cache = load_cache(song)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/kick_attacks",
            "engine": "mix audio: 40-120 Hz 5 ms-RMS rise >= %.0f dB over the previous 5-40 ms with a coincident 2-5 kHz click "
                      "(pitch drop as tie-break); weaker+duller repeats at a recurring offset labelled echo; "
                      "attacks > 1/4 beat off beats.json kept at x%.1f confidence" % (detect.LOW_RISE_DB, detect.OFF_GRID_PENALTY),
            "inputs": ["data/songs/<song>.mp3", "beats.json"],
            "params": {"low_rise_db": detect.LOW_RISE_DB, "click_db": detect.CLICK_DB, "click_min_db": detect.CLICK_MIN_DB,
                       "level_floor": detect.LEVEL_FLOOR, "echo_weaker": detect.ECHO_WEAKER,
                       "echo_min_pairs": detect.ECHO_MIN_PAIRS, "off_grid_frac": detect.OFF_GRID_FRAC},
            "confidence_reason": "weighted rise/click/pitch/level evidence, not calibrated against ground truth",
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "events": cache["events"],
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        ev = export(song)["events"]
        echoes = sum(1 for e in ev if e["echo_of"] is not None)
        print(f"exported {song} — {len(ev) - echoes} kick attacks, {echoes} echoes")
