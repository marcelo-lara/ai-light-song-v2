"""Write `reference/proposals/phrase_periodicity.json` — the timeline lane input.

One block per operator hint (or published section where no hints exist), each
carrying:

  * `regime`  -> through-composed / bar-loop / half-bar-loop
  * `period`  -> repeat unit in bars (1.0 / 0.5) or null. A null renders in the
    lane as "no phrase structure detected", never a fabricated number.

Plus `phrase_lengths` — the per-stem song-level phrase length + prominence, so
the lane's summary can name the dominant phrase. A proposal to audition against
Human Hints, never ground truth.
"""
from __future__ import annotations

import datetime
import json

from . import features as feat_mod
from . import paths
from . import periodicity as per

SCHEMA_VERSION = "1.0"


def export(song: str) -> dict:
    cache = feat_mod.load_cache(song)
    starts = cache["block_starts"]
    ends = cache["block_ends"]
    titles = [str(t) for t in cache["block_titles"]]
    source = str(cache["block_source"][0]) if len(cache["block_source"]) else "none"

    blocks = []
    for s, e, title in zip(starts, ends, titles):
        bars = per.bars_in_span(cache, float(s), float(e), "z_composite")
        reg, period = per.regime(bars)
        blocks.append(
            {
                "start_s": round(float(s), 3),
                "end_s": round(float(e), 3),
                "title": title,
                "regime": reg,
                "period": period,
                "n_bars": int(len(bars)),
            }
        )

    phrase_lengths = {}
    for stem in paths.STEM_IDS:
        p, prom = per.phrase_length(cache[f"z_{stem}"])
        phrase_lengths[stem] = {
            "phrase_bars": p,
            "prominence": round(prom, 4),
            "detected": p is not None,
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/phrase_periodicity",
            "engine": "per-bar 16-slot z-normalised energy profile -> bar-sequence autocorrelation (period only)",
            "bar_grid": "beats.json downbeats",
            "envelope": "loudness.json 20 ms per-stem RMS",
            "block_source": source,
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "phrase_lengths": phrase_lengths,
        "blocks": blocks,
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        detected = [k for k, v in payload["phrase_lengths"].items() if v["detected"]]
        print(
            f"exported {song} — {len(payload['blocks'])} blocks, "
            f"phrase detected on: {', '.join(detected) or 'none'}"
        )
