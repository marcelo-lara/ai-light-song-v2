"""Scoring harness for the `drops` compare target.

Precision/recall of detected drops against timed human drop hints in
``reference/human/human_hints.json``, with a bar-scale onset tolerance.

Timed-only: the target used to degrade to a `presence` check against the
song-level `has_drop` fact when no timed hints existed, but that check passes
by construction (any detector that fires at least once "matches" a
`has_drop: true` song) and asserted nothing about *when*. Plan v3.0 item 10
removed it. A song with no timed drop hints now reports `skipped` with the
reason, same as a song with no reference file at all.

The sibling `form` target (section-boundary F-measure against
`reference/human/human_hints.json` boundary labels) is gone as of the same
item: it reported `mode: "unlabelled"`, `labelled_boundary_count: 0` on all
four gold songs, and `validate-sections` against
`reference/moises/segments.json` supersedes it with real labelled evidence.

This target is advisory: like `sections` it never flips the pipeline exit
code (its ground truth is an incomplete gold set).
"""

from __future__ import annotations

import re
from dataclasses import replace

from analyzer.io import read_json, write_json
from analyzer.paths import SongPaths

from .utils import ValidationResult, skipped_result

# Onset tolerance for matching a detected drop to a labelled drop. One bar at
# 120 BPM in 4/4 is 2.0 s; ±1.0 s is half a bar, tight enough to be meaningful
# without punishing sub-beat detector jitter.
DROP_TOLERANCE_SECONDS = 1.0

_DROP_TYPES = {"drop", "beat_drop", "bass_drop", "drop_hit"}
_FAKE_DROP_TYPES = {"fake_drop", "false_drop"}
_DROP_WORD = re.compile(r"\bdrop\b", re.IGNORECASE)
_FAKE_WORD = re.compile(r"\bfake\b|\bfalse\b|\bwithheld\b", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Ground-truth loading
# --------------------------------------------------------------------------- #

def load_human_hints(paths: SongPaths) -> list[dict]:
    path = paths.reference("human", "human_hints.json")
    if not path.exists():
        return []
    payload = read_json(path)
    hints = payload.get("human_hints") if isinstance(payload, dict) else None
    return hints if isinstance(hints, list) else []


def labelled_drop_times(hints: list[dict]) -> list[float]:
    """Timed drop labels: hints whose title/summary names a drop but not a fake one."""
    times: list[float] = []
    for hint in hints:
        text = f"{hint.get('title', '')} {hint.get('summary', '')}"
        if _DROP_WORD.search(text) and not _FAKE_WORD.search(text):
            try:
                times.append(float(hint["start_time"]))
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(times)


# --------------------------------------------------------------------------- #
# Detected-output loading
# --------------------------------------------------------------------------- #

def _iter_timeline_events(timeline: dict):
    for event in timeline.get("events", []):
        if isinstance(event, dict):
            yield event


def detected_drops(timeline: dict) -> list[dict]:
    out: list[dict] = []
    for event in _iter_timeline_events(timeline):
        etype = str(event.get("type", "")).lower()
        is_drop = etype in _DROP_TYPES or (_DROP_WORD.search(etype.replace("_", " ")) and etype not in _FAKE_DROP_TYPES)
        if etype in _FAKE_DROP_TYPES:
            continue
        # Composite events (v1.1 item 4.1) carry phases; an "impact" phase marks
        # the drop instant. Fall back to start_time otherwise.
        if is_drop or (event.get("phases") and any(str(p.get("phase")) == "impact" for p in event["phases"])):
            impact_t = None
            for phase in event.get("phases", []) or []:
                if str(phase.get("phase")) == "impact":
                    impact_t = float(phase.get("start_time", event.get("start_time", 0.0)))
            out.append({
                "time": impact_t if impact_t is not None else float(event.get("start_time", 0.0)),
                "type": etype,
                "confidence": float(event.get("confidence", 0.0)),
            })
    return sorted(out, key=lambda row: row["time"])


def detected_fake_drops(timeline: dict) -> list[dict]:
    return [
        {"time": float(e.get("start_time", 0.0)), "type": str(e.get("type", ""))}
        for e in _iter_timeline_events(timeline)
        if str(e.get("type", "")).lower() in _FAKE_DROP_TYPES
    ]


# --------------------------------------------------------------------------- #
# Matching / metrics
# --------------------------------------------------------------------------- #

def _greedy_match(predicted: list[float], labels: list[float], tolerance: float) -> list[tuple[int, int, float]]:
    """Greedy nearest-first one-to-one matching. Returns (pred_idx, label_idx, delta)."""
    candidates: list[tuple[float, int, int]] = []
    for pi, pt in enumerate(predicted):
        for li, lt in enumerate(labels):
            delta = pt - lt
            if abs(delta) <= tolerance:
                candidates.append((abs(delta), pi, li))
    candidates.sort()
    used_pred: set[int] = set()
    used_label: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for _, pi, li in candidates:
        if pi in used_pred or li in used_label:
            continue
        used_pred.add(pi)
        used_label.add(li)
        matches.append((pi, li, predicted[pi] - labels[li]))
    return matches


def _prf(true_positives: int, predicted: int, labelled: int) -> dict:
    precision = true_positives / predicted if predicted else None
    recall = true_positives / labelled if labelled else None
    if precision and recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0 if (predicted or labelled) else None
    return {
        "true_positives": true_positives,
        "predicted": predicted,
        "labelled": labelled,
        "precision": _round(precision),
        "recall": _round(recall),
        "f1": _round(f1),
    }


def _round(value, digits: int = 4):
    return None if value is None else round(float(value), digits)


def score_drops(timeline: dict, hints: list[dict],
                tolerance: float = DROP_TOLERANCE_SECONDS) -> dict:
    detected = detected_drops(timeline)
    fake = detected_fake_drops(timeline)
    labels = labelled_drop_times(hints)

    result: dict = {
        "target": "drops",
        "tolerance_seconds": tolerance,
        "detected_count": len(detected),
        "fake_drop_count": len(fake),
        "detected_times": [round(d["time"], 3) for d in detected],
        "labelled_count": len(labels),
    }

    if labels:
        matches = _greedy_match([d["time"] for d in detected], labels, tolerance)
        result["metrics"] = _prf(len(matches), len(detected), len(labels))
        result["match_deltas"] = [round(delta, 3) for _, _, delta in matches]
        result["mode"] = "timed"
    else:
        # Timed-only (plan v3.0 item 10): no `has_drop`-fact presence fallback
        # here — a detector that fires once on any `has_drop: true` song would
        # pass that check by construction without ever being scored on *when*.
        result["mode"] = "unlabelled"

    # B3 symmetry check: fake_drop must not outnumber drop.
    result["fake_outnumbers_drop"] = len(fake) > len(detected)
    return result


# --------------------------------------------------------------------------- #
# ValidationResult adapter + artifact
# --------------------------------------------------------------------------- #

def _result_from_score(score: dict, reference_file: str | None) -> ValidationResult:
    if score.get("mode") != "timed":
        return replace(skipped_result(), diagnostics={"reason": "no timed human drop hints", "score": score})

    m = score["metrics"]
    checks = [
        {"check": "drop recall >= 0.5", "passed": (m["recall"] or 0) >= 0.5, "recall": m["recall"]},
        {"check": "drop precision >= 0.5", "passed": (m["precision"] or 0) >= 0.5, "precision": m["precision"]},
        {"check": "fake_drop does not outnumber drop", "passed": not score["fake_outnumbers_drop"],
         "fake": score["fake_drop_count"], "drop": score["detected_count"]},
    ]

    matched = sum(1 for c in checks if c["passed"])
    mismatched = len(checks) - matched
    return ValidationResult(
        status="passed" if mismatched == 0 else "failed",
        matched=matched,
        mismatched=mismatched,
        match_ratio=(matched / len(checks)) if checks else None,
        details=checks,
        reference_file=reference_file,
        diagnostics={"score": score},
    )


def validate_drops(paths: SongPaths) -> ValidationResult:
    timeline_path = paths.timeline_output_path
    if not timeline_path.exists():
        return skipped_result()
    timeline = read_json(timeline_path)
    hints = load_human_hints(paths)
    score = score_drops(timeline, hints)
    _write_score_artifact(paths, "drops", score)
    return _result_from_score(score, str(paths.reference("human", "human_hints.json")))


def _write_score_artifact(paths: SongPaths, target: str, score: dict) -> None:
    out_path = paths.artifact("validation", f"{target}_score.json")
    write_json(out_path, {"schema_version": "1.1", "song_name": paths.song_name, **score})
