"""Scoring harness for the v1.1 `form` and `drops` compare targets.

These two targets score the structural read of a song against hand-authored
ground truth in ``reference/human/``:

* ``drops`` — precision/recall of detected drops against timed human drop hints,
  with a bar-scale onset tolerance. When only the song-level ``has_drop`` fact is
  available (no timed hints yet), it degrades to a presence check.
* ``form`` — section-boundary F-measure, ``form_role`` accuracy over matched
  boundaries, ``form_family`` exact match, and a confidence-calibration table.

Both targets are advisory: like ``sections`` they never flip the pipeline exit
code. They exist so that a later human labelling pass (plan item 0.2 / D1) can
retroactively validate items 1.x–3.x. Until labels land, the targets report
``skipped`` with the reason.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from analyzer.io import read_json, write_json
from analyzer.paths import SongPaths

from .utils import ValidationResult, skipped_result

# Onset tolerance for matching a detected drop to a labelled drop. One bar at
# 120 BPM in 4/4 is 2.0 s; ±1.0 s is half a bar, tight enough to be meaningful
# without punishing sub-beat detector jitter.
DROP_TOLERANCE_SECONDS = 1.0
# Section-boundary match tolerance. Matches the analyzer's --tolerance-seconds
# default so `form` and `sections` agree on what "the same boundary" means.
BOUNDARY_TOLERANCE_SECONDS = 2.0

_DROP_TYPES = {"drop", "beat_drop", "bass_drop", "drop_hit"}
_FAKE_DROP_TYPES = {"fake_drop", "false_drop"}
_DROP_WORD = re.compile(r"\bdrop\b", re.IGNORECASE)
_FAKE_WORD = re.compile(r"\bfake\b|\bfalse\b|\bwithheld\b", re.IGNORECASE)

CONFIDENCE_BUCKETS = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01))


# --------------------------------------------------------------------------- #
# Ground-truth loading
# --------------------------------------------------------------------------- #

def load_song_facts(paths: SongPaths) -> dict:
    """Return the ``facts`` map from ``reference/human/song_facts.json`` or {}."""
    path = paths.reference("human", "song_facts.json")
    if not path.exists():
        return {}
    payload = read_json(path)
    facts = payload.get("facts") if isinstance(payload, dict) else None
    return facts if isinstance(facts, dict) else {}


def _fact_value(facts: dict, name: str):
    entry = facts.get(name)
    if isinstance(entry, dict):
        return entry.get("value")
    return entry


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


def labelled_boundaries(hints: list[dict]) -> list[dict]:
    """Section-boundary labels.

    A boundary label is a hint carrying an explicit ``form_role`` (the intended
    role of the section that *starts* at ``start_time``) or ``section_boundary:
    true``. This is the shape plan item 0.2 writes; three of the four gold tracks
    do not have it yet.
    """
    boundaries: list[dict] = []
    for hint in hints:
        role = hint.get("form_role")
        if role is None and not hint.get("section_boundary"):
            continue
        try:
            boundaries.append({"time": float(hint["start_time"]), "form_role": role})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(boundaries, key=lambda row: row["time"])


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
        summary = str(event.get("summary", ""))
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


def _sections_list(sections: dict) -> list[dict]:
    rows = sections.get("sections", []) if isinstance(sections, dict) else []
    return [row for row in rows if isinstance(row, dict)]


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


def score_drops(timeline: dict, hints: list[dict], facts: dict,
                tolerance: float = DROP_TOLERANCE_SECONDS) -> dict:
    detected = detected_drops(timeline)
    fake = detected_fake_drops(timeline)
    labels = labelled_drop_times(hints)
    has_drop = _fact_value(facts, "has_drop")

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
    elif has_drop is not None:
        result["mode"] = "presence"
        result["presence_expected"] = bool(has_drop)
        result["presence_detected"] = len(detected) > 0
        result["presence_ok"] = bool(has_drop) == (len(detected) > 0)
    else:
        result["mode"] = "unlabelled"

    # B3 symmetry check: fake_drop must not outnumber drop.
    result["fake_outnumbers_drop"] = len(fake) > len(detected)
    return result


def score_form(sections: dict, hints: list[dict], facts: dict,
               tolerance: float = BOUNDARY_TOLERANCE_SECONDS) -> dict:
    rows = _sections_list(sections)
    # Boundary = start of every section after the first.
    predicted_boundaries = [float(row.get("start", row.get("start_time", 0.0))) for row in rows[1:]]
    predicted_roles = [row.get("form_role") for row in rows[1:]]

    labelled = labelled_boundaries(hints)
    label_times = [row["time"] for row in labelled]

    family_pred = sections.get("form_family")
    if isinstance(family_pred, dict):
        family_pred = family_pred.get("value") or family_pred.get("family")
    family_label = _fact_value(facts, "form_family")

    result: dict = {
        "target": "form",
        "tolerance_seconds": tolerance,
        "predicted_boundary_count": len(predicted_boundaries),
        "labelled_boundary_count": len(label_times),
        "form_family_predicted": family_pred,
        "form_family_labelled": family_label,
        "form_family_match": (family_label is not None and family_pred == family_label),
    }

    if label_times:
        matches = _greedy_match(predicted_boundaries, label_times, tolerance)
        result["boundary_metrics"] = _prf(len(matches), len(predicted_boundaries), len(label_times))
        # form_role accuracy over matched boundaries
        role_hits = 0
        role_total = 0
        for pi, li, _ in matches:
            labelled_role = labelled[li].get("form_role")
            if labelled_role is None:
                continue
            role_total += 1
            if predicted_roles[pi] == labelled_role:
                role_hits += 1
        result["form_role"] = {
            "matched_boundaries_with_role": role_total,
            "correct": role_hits,
            "accuracy": _round(role_hits / role_total) if role_total else None,
        }
        result["role_mode"] = "labelled"

    result["mode"] = "labelled" if (label_times or family_label is not None) else "unlabelled"
    result["confidence_calibration"] = confidence_calibration(rows, label_times, tolerance)
    return result


def confidence_calibration(rows: list[dict], label_times: list[float],
                           tolerance: float = BOUNDARY_TOLERANCE_SECONDS) -> dict:
    """Bucket sections by predicted boundary confidence and report observed
    accuracy (fraction whose start aligns to a labelled boundary) per bucket.

    Only meaningful once boundary labels exist; with no labels the observed
    column is null but the predicted distribution is still reported (it shows
    whether item 3.1 spread confidence across its range).
    """
    buckets: list[dict] = []
    for low, high in CONFIDENCE_BUCKETS:
        members = [
            row for row in rows[1:]
            if low <= float(row.get("confidence", 0.0)) < high
        ]
        observed = None
        if label_times and members:
            aligned = sum(
                1 for row in members
                if any(abs(float(row.get("start", row.get("start_time", 0.0))) - lt) <= tolerance
                       for lt in label_times)
            )
            observed = round(aligned / len(members), 4)
        buckets.append({
            "range": [low, round(high, 2)],
            "section_count": len(members),
            "observed_alignment": observed,
        })
    confidences = [float(row.get("confidence", 0.0)) for row in rows[1:]]
    spread = (max(confidences) - min(confidences)) if confidences else 0.0
    return {"buckets": buckets, "predicted_spread": round(spread, 4)}


# --------------------------------------------------------------------------- #
# ValidationResult adapters + artifact
# --------------------------------------------------------------------------- #

def _result_from_score(score: dict, reference_file: str | None) -> ValidationResult:
    mode = score.get("mode")
    if mode in {"unlabelled", None}:
        return replace(skipped_result(), diagnostics={"reason": "no human labels", "score": score})

    checks: list[dict] = []
    if score["target"] == "drops":
        if mode == "timed":
            m = score["metrics"]
            checks.append({"check": "drop recall >= 0.5", "passed": (m["recall"] or 0) >= 0.5, "recall": m["recall"]})
            checks.append({"check": "drop precision >= 0.5", "passed": (m["precision"] or 0) >= 0.5, "precision": m["precision"]})
        elif mode == "presence":
            checks.append({"check": "drop presence matches human fact", "passed": score["presence_ok"],
                           "expected": score["presence_expected"], "detected": score["presence_detected"]})
        checks.append({"check": "fake_drop does not outnumber drop", "passed": not score["fake_outnumbers_drop"],
                       "fake": score["fake_drop_count"], "drop": score["detected_count"]})
    else:  # form
        if score.get("form_family_labelled") is not None:
            checks.append({"check": "form_family exact match", "passed": score["form_family_match"],
                           "predicted": score["form_family_predicted"], "labelled": score["form_family_labelled"]})
        bm = score.get("boundary_metrics")
        if bm:
            checks.append({"check": "boundary F1 >= 0.6", "passed": (bm["f1"] or 0) >= 0.6, "f1": bm["f1"]})
        fr = score.get("form_role")
        if fr and fr.get("accuracy") is not None:
            checks.append({"check": "form_role accuracy >= 0.6", "passed": fr["accuracy"] >= 0.6, "accuracy": fr["accuracy"]})

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
    facts = load_song_facts(paths)
    score = score_drops(timeline, hints, facts)
    _write_score_artifact(paths, "drops", score)
    return _result_from_score(score, str(paths.reference("human", "human_hints.json")))


def validate_form(paths: SongPaths) -> ValidationResult:
    sections_path = paths.artifact("section_segmentation", "sections.json")
    if not sections_path.exists():
        return skipped_result()
    sections = read_json(sections_path)
    hints = load_human_hints(paths)
    facts = load_song_facts(paths)
    score = score_form(sections, hints, facts)
    _write_score_artifact(paths, "form", score)
    return _result_from_score(score, str(paths.reference("human", "song_facts.json")))


def _write_score_artifact(paths: SongPaths, target: str, score: dict) -> None:
    out_path = paths.artifact("validation", f"{target}_score.json")
    write_json(out_path, {"schema_version": "1.1", "song_name": paths.song_name, **score})
