"""Write `reference/proposals/voice_multiplicity.json` — the timeline lane input.

Blocks label regions as solo (low multiplicity), stacked (high multiplicity),
or ambiguous (between thresholds). A proposal to audition against Human Hints,
never ground truth.
"""
from __future__ import annotations

import json

import numpy as np

from . import features as feat_mod
from . import paths

SCHEMA_VERSION = "1.0"
SOLO_THRESHOLD = -0.5
STACKED_THRESHOLD = 0.5
MIN_BLOCK_S = 0.5


def export(song: str) -> dict:
    """Export one song's voice multiplicity blocks."""
    cache = feat_mod.load_cache(song)

    times = np.array(cache["times"], dtype=float)
    multiplicity = np.array(cache["multiplicity"], dtype=float)
    present = np.array(cache["present"], dtype=bool)
    width_z = np.array(cache["width_z"], dtype=float)
    corr_z = np.array(cache["corr_z"], dtype=float)

    n_frames = len(times)
    duration = float(times[-1]) + feat_mod.HOP_S if len(times) > 0 else 0.0

    # Build frames list (all frames, with None where not present)
    frames = []
    for i in range(n_frames):
        frame = {
            "time": float(times[i]),
        }
        if present[i]:
            frame["multiplicity"] = float(multiplicity[i]) if not np.isnan(multiplicity[i]) else None
            frame["width_z"] = float(width_z[i]) if not np.isnan(width_z[i]) else None
            frame["corr_z"] = float(corr_z[i]) if not np.isnan(corr_z[i]) else None
            frame["present"] = True
        else:
            frame["multiplicity"] = None
            frame["width_z"] = None
            frame["corr_z"] = None
            frame["present"] = False
        frames.append(frame)

    # Build blocks from present frames only
    blocks = []
    i = 0
    while i < n_frames:
        if not present[i]:
            i += 1
            continue

        # Start of a potential block
        start_idx = i
        start_time = times[i]

        # Determine kind based on first present frame
        mult = multiplicity[i]
        if mult >= STACKED_THRESHOLD:
            kind = "stacked"
        elif mult <= SOLO_THRESHOLD:
            kind = "solo"
        else:
            # Ambiguous frame, skip it
            i += 1
            continue

        # Extend block while frames have same kind
        block_mults = [mult]
        while i + 1 < n_frames:
            i += 1
            if not present[i]:
                # End of block at this gap
                break
            mult = multiplicity[i]
            # Check if same kind
            is_stacked = mult >= STACKED_THRESHOLD
            is_solo = mult <= SOLO_THRESHOLD
            if kind == "stacked" and is_stacked:
                block_mults.append(mult)
            elif kind == "solo" and is_solo:
                block_mults.append(mult)
            else:
                # Kind changed, rewind
                i -= 1
                break

        end_idx = i
        end_time = times[end_idx] + feat_mod.HOP_S

        # Only emit if block is long enough
        duration_s = end_time - start_time
        if duration_s >= MIN_BLOCK_S and block_mults:
            mean_mult = float(np.mean(block_mults))
            confidence = float(np.minimum(1.0, np.abs(mean_mult) / 2.0))
            blocks.append({
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "kind": kind,
                "mean_multiplicity": round(mean_mult, 6),
                "confidence": round(confidence, 3),
            })

        i += 1

    # Metadata
    n_present = int(np.sum(present))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/voice_multiplicity",
            "engine": "stereo mid/side width + L-R correlation on the vocals stem, per-song z-scored",
            "source": "artifacts/stems/vocals.wav",
            "note": "Per-song z-scores only. Absolute width is NOT comparable across songs.",
        },
        "metadata": {
            "interval_ms": 50,
            "total_frames": n_frames,
            "present_frames": n_present,
        },
        "frames": frames,
        "blocks": blocks,
    }

    # Write to reference/proposals/
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")

    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        print(f"exported {song} — {len(payload['blocks'])} blocks")
