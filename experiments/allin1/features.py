"""Derive every usable feature from one cached allin1 run.

The model returns four things: a tempo, a beat grid, a downbeat grid, and a
segmentation labelled from the Harmonix vocabulary. Everything below is derived
from those, deterministically, with no second model and no audio. Kept separate
from `model.py` so the derivation can change without re-running the GPU step.

Two derivations carry most of the value:

* **sections** — allin1 emits one segment per 8-bar phrase, so a 32-bar chorus
  arrives as four consecutive `chorus` rows. Merging equal-labelled neighbours
  is what turns the phrase grid into song form; the musically real boundary is
  only where the label actually changes.
* **transitions** — the instants where the label changes, carrying the label
  *pair*. A cue is defined by a change, and the pair says what kind of change it
  is. This is the field the shipped `sections.json` has no equivalent of.

Honesty (constitution §2): nothing here invents a label. Where allin1
degenerates — instrumental tracks outside its Harmonix pop training
distribution, where it emits one or two labels for the whole song — the
derivation says so in `labelling.status` and every section is marked
`function_status: "unknown"` rather than carrying a confident wrong name.
"""
from __future__ import annotations

import json
import statistics
from typing import Any

from .paths import essentia_beats_path, human_hints_path

#: The Harmonix vocabulary allin1 predicts, plus its two sentinel rows.
SENTINELS = ("start", "end")
FUNCTIONS = ("intro", "verse", "chorus", "bridge", "inst", "solo", "break", "outro")

#: Typical intensity ordering of the vocabulary, used only to say whether a
#: transition goes up, down, or sideways. It is a reading convention for the
#: review lane, NOT a measured claim: `kind` is derived from the two labels and
#: nothing else, and it inherits every error the labels make.
ENERGY_RANK = {
    "intro": 1, "break": 1, "outro": 1,
    "verse": 2, "bridge": 2,
    "inst": 3, "solo": 3,
    "chorus": 4,
}

#: A song is called degenerate when allin1 gives it fewer than this many
#: distinct functional labels, or one label covers more than DOMINANT_MAX of its
#: duration. Both thresholds are chosen to catch the three corpus tracks the
#: survey identified by hand (Armin - Revolution, Chimera - Hana, _test_song)
#: and nothing else; see README "Measurement 3".
MIN_DISTINCT_LABELS = 3
DOMINANT_MAX = 0.75


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


# ------------------------------------------------------------------ tempo --


def tempo(raw: dict) -> dict:
    beats = raw["beats"]
    periods = [b - a for a, b in zip(beats, beats[1:])]
    median = statistics.median(periods) if periods else float("nan")
    return {
        "bpm": raw["bpm"],
        "beat_count": len(beats),
        "median_beat_period_s": _round(median),
        # Spread of the beat period over the whole song. A steady four-on-the-
        # floor track sits near zero; a large value means the grid wanders and
        # any bar arithmetic built on it is suspect.
        "beat_period_stdev_s": _round(statistics.pstdev(periods)) if len(periods) > 1 else 0.0,
    }


# --------------------------------------------------------------- bar grid --


def bar_grid(raw: dict) -> dict:
    """Downbeats numbered from 1, plus the meter allin1 implies.

    Bars are 1-indexed to match the repo's convention. The meter is read off the
    largest beat position the model emitted rather than assumed to be 4.
    """
    downbeats = raw["downbeats"]
    positions = raw["beat_positions"]
    meter = max(positions) if positions else 4
    spacings = [b - a for a, b in zip(downbeats, downbeats[1:])]
    return {
        "meter": meter,
        "bar_count": len(downbeats),
        "median_bar_length_s": _round(statistics.median(spacings)) if spacings else None,
        "downbeats": [_round(t) for t in downbeats],
    }


def _bar_index(downbeats: list[float], time: float, tol: float = 0.12) -> int | None:
    """1-indexed bar containing `time`, or None when it is before the first bar."""
    if not downbeats:
        return None
    index = None
    for i, d in enumerate(downbeats):
        if time >= d - tol:
            index = i + 1
        else:
            break
    return index


def _bars_between(downbeats: list[float], start: float, end: float, tol: float = 0.12) -> int:
    return sum(1 for d in downbeats if start - tol <= d < end - tol)


# ---------------------------------------------------------------- phrases --


def phrases(raw: dict, downbeats: list[float]) -> list[dict]:
    """The model's own segment rows — its 8-bar phrase grid, unmerged.

    Kept in the output because the phrase edges are the reason allin1's
    boundaries are clean: the model is not localising an event, it is placing a
    phrase edge. Their spacing is also the cheapest check that the grid is sane.
    """
    out = []
    index = 0
    for seg in raw["segments"]:
        if seg["label"] in SENTINELS:
            continue
        index += 1
        out.append({
            "id": f"phrase-{index:03d}",
            "start_s": _round(seg["start"]),
            "end_s": _round(seg["end"]),
            "label": seg["label"],
            "start_bar": _bar_index(downbeats, seg["start"]),
            "bars": _bars_between(downbeats, seg["start"], seg["end"]),
        })
    return out


# --------------------------------------------------------------- sections --


def sections(phrase_rows: list[dict], downbeats: list[float]) -> list[dict]:
    """Merge consecutive equal-labelled phrases into song-form sections.

    `occurrence` and `repeat_of` are *label repetition*, not acoustic identity:
    they say "this is the third thing allin1 called a chorus", which is weaker
    than "this is the same music as the first chorus". Real identity needs a
    second model (the survey's MERT clustering) and is not part of this
    experiment — the field is named so it cannot be mistaken for it.
    """
    runs: list[dict] = []
    for row in phrase_rows:
        if runs and runs[-1]["label"] == row["label"] and abs(runs[-1]["end_s"] - row["start_s"]) < 0.25:
            runs[-1]["end_s"] = row["end_s"]
            runs[-1]["phrases"].append(row["id"])
        else:
            runs.append({"label": row["label"], "start_s": row["start_s"],
                         "end_s": row["end_s"], "phrases": [row["id"]]})

    # Totals first, so a label that occurs once is named `bridge` rather than
    # `bridge 1` while a returning one is numbered.
    totals: dict[str, int] = {}
    for run in runs:
        totals[run["label"]] = totals.get(run["label"], 0) + 1

    seen: dict[str, str] = {}
    counts: dict[str, int] = {}
    out = []
    for index, run in enumerate(runs, 1):
        label = run["label"]
        counts[label] = counts.get(label, 0) + 1
        section_id = f"allin1-{index:03d}"
        first = seen.setdefault(label, section_id)
        out.append({
            "id": section_id,
            "function": label,
            "occurrence": counts[label],
            "occurrence_count": totals[label],
            "name": label if totals[label] == 1 else f"{label} {counts[label]}",
            "start_s": run["start_s"],
            "end_s": run["end_s"],
            "duration_s": _round(run["end_s"] - run["start_s"]),
            "start_bar": _bar_index(downbeats, run["start_s"]),
            "bars": _bars_between(downbeats, run["start_s"], run["end_s"]),
            "phrase_count": len(run["phrases"]),
            "phrase_ids": run["phrases"],
            # Same *label*, not verified same music. See the docstring.
            "same_label_as": None if first == section_id else first,
        })
    return out


# ----------------------------------------------------------- transitions --


def transitions(section_rows: list[dict], downbeats: list[float],
                essentia_beats: list[float], bar_length: float | None) -> list[dict]:
    """One row per section boundary — the cue-defining instants.

    Each row carries the label pair, because that is what says *what kind* of
    change this is, and the offset to the nearest essentia beat, because that is
    the grid every cue in this repo is snapped to. Measurement 4 of the drop
    survey found every human impact lands on an essentia beat while no two
    downbeat trackers agree, so `on_downbeat` is reported and never relied on.
    """
    # A transition is an instant, but a review lane needs something to draw and
    # something to click. The block spans the bar the change happens in, which
    # is the musical unit a cue is placed against — never wider than the section
    # it opens.
    span = bar_length if bar_length and bar_length > 0 else 2.0
    out = []
    for index, (prev, cur) in enumerate(zip(section_rows, section_rows[1:]), 1):
        time = cur["start_s"]
        rank_from = ENERGY_RANK.get(prev["function"], 0)
        rank_to = ENERGY_RANK.get(cur["function"], 0)
        beat_offset = _nearest_offset(essentia_beats, time)
        downbeat_offset = _nearest_offset(downbeats, time)
        out.append({
            "id": f"allin1-t-{index:03d}",
            "time_s": time,
            "start_s": time,
            "end_s": _round(min(time + span, cur["end_s"])),
            "from": prev["function"],
            "to": cur["function"],
            "from_name": prev["name"],
            "to_name": cur["name"],
            "pair": f"{prev['function']} → {cur['function']}",
            # Reading convention only — derived from ENERGY_RANK, not measured.
            "kind": "lift" if rank_to > rank_from else "release" if rank_to < rank_from else "shift",
            "bar": cur["start_bar"],
            "essentia_beat_offset_s": beat_offset,
            "on_downbeat": downbeat_offset is not None and abs(downbeat_offset) <= 0.12,
            "leaves_bars": prev["bars"],
            "enters_bars": cur["bars"],
        })
    return out


def _nearest_offset(grid: list[float], time: float) -> float | None:
    """Signed distance from `time` to the nearest grid point (grid - time)."""
    if not grid:
        return None
    return _round(min(grid, key=lambda g: abs(g - time)) - time)


# --------------------------------------------------------------- honesty --


def labelling(section_rows: list[dict], duration: float) -> dict:
    """Is this song inside the distribution allin1 can name?

    The failure mode is not a wrong boundary, it is a confident wrong *name*:
    on instrumental trance with no verse/chorus vocal contrast the model emits
    one or two labels for the whole track. That is detectable without any
    ground truth, which is what lets the artifact say `unknown` instead.
    """
    if not section_rows or duration <= 0:
        return {"status": "empty", "distinct_labels": 0, "dominant_label": None,
                "dominant_share": None, "reason": "allin1 returned no sections"}
    share: dict[str, float] = {}
    for row in section_rows:
        share[row["function"]] = share.get(row["function"], 0.0) + row["duration_s"]
    dominant, dominant_seconds = max(share.items(), key=lambda kv: kv[1])
    dominant_share = dominant_seconds / duration
    distinct = len(share)

    reasons = []
    if distinct < MIN_DISTINCT_LABELS:
        reasons.append(f"only {distinct} distinct label(s)")
    if dominant_share > DOMINANT_MAX:
        reasons.append(f"`{dominant}` covers {dominant_share:.0%} of the song")
    return {
        "status": "degenerate" if reasons else "ok",
        "distinct_labels": distinct,
        "dominant_label": dominant,
        "dominant_share": _round(dominant_share, 3),
        "reason": "; ".join(reasons) or None,
        "note": ("Section names on this song are not trustworthy — allin1 is outside "
                 "its training distribution here. Boundaries may still be usable."
                 if reasons else None),
    }


# ------------------------------------------------------------- reference --


def essentia_beats(song: str) -> list[float]:
    path = essentia_beats_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return [float(b["time"]) for b in payload.get("beats", [])]


def human_impacts(song: str) -> list[float]:
    """The hand-placed `drop impact` instants — the only hard labels in the repo."""
    path = human_hints_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return sorted(
        float(h["start_time"])
        for h in payload.get("human_hints", [])
        if str(h.get("title", "")).strip().casefold() == "drop impact"
    )


def beat_agreement(allin1_beats: list[float], ess_beats: list[float]) -> dict:
    """How far allin1's beat grid sits from the grid the pipeline already ships."""
    if not allin1_beats or not ess_beats:
        return {"comparable": False}
    errors = [abs(min(ess_beats, key=lambda g: abs(g - b)) - b) for b in allin1_beats]
    return {
        "comparable": True,
        "median_abs_offset_s": _round(statistics.median(errors)),
        "within_0.05s": sum(1 for e in errors if e <= 0.05),
        "beats_compared": len(errors),
        "essentia_beat_count": len(ess_beats),
    }


# ----------------------------------------------------------------- bundle --


def derive(song: str, raw: dict) -> dict[str, Any]:
    """Everything above, in one dict, for one song."""
    grid = bar_grid(raw)
    downbeats = raw["downbeats"]
    phrase_rows = phrases(raw, downbeats)
    section_rows = sections(phrase_rows, downbeats)
    ess = essentia_beats(song)
    duration = section_rows[-1]["end_s"] - section_rows[0]["start_s"] if section_rows else 0.0
    return {
        "tempo": tempo(raw),
        "bar_grid": grid,
        "beat_agreement": beat_agreement(raw["beats"], ess),
        "labelling": labelling(section_rows, duration),
        "sections": section_rows,
        "transitions": transitions(section_rows, downbeats, ess,
                                   grid["median_bar_length_s"]),
        "phrases": phrase_rows,
    }
