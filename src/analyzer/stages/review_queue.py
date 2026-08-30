"""v1.1 item 5.1 — machine review queue.

`build_review_queue` writes ``artifacts/validation/review_queue.json``: the open
questions this run could not settle, ranked so the highest-leverage question is
first. Each entry names the field in question, its competing candidates with
scores, the timestamps of the ambiguous evidence, and why confidence was low.

Direction of flow (constitution + refinement item 7): the analyzer proposes into
``validation/``; a human disposes into ``reference/human/song_facts.json``. The
analyzer never writes into ``reference/``.
"""

from __future__ import annotations

from analyzer.io import read_json, write_json
from analyzer.paths import SongPaths
from analyzer.stages.validation.form_drops import load_song_facts

FORM_FAMILY_LOW_CONFIDENCE = 0.55
FORM_ROLE_THIN_MARGIN = 0.12

# Genre labels that broadly agree with each form_family, for the R1a
# disagreement flag. A mismatch is a review signal, never a correction.
_FAMILY_GENRE_HINTS = {
    "dance_form": {"dance", "electronic", "house", "techno", "trance", "edm", "drum and bass", "dubstep"},
    "song_form": {"pop", "rock", "folk", "singer-songwriter", "r&b", "soul", "country", "indie"},
}


def _question(field, candidates, evidence_times, reason, leverage):
    return {
        "field": field,
        "candidates": candidates,
        "evidence_timestamps": [round(float(t), 3) for t in evidence_times],
        "reason_low_confidence": reason,
        "leverage": round(float(leverage), 4),
    }


def build_review_queue(
    paths: SongPaths,
    sections_payload: dict,
    genre_result: dict | None,
    timeline_payload: dict | None,
) -> dict:
    facts = load_song_facts(paths)
    questions: list[dict] = []
    sections = [s for s in sections_payload.get("sections", []) if isinstance(s, dict)]

    # --- form_family --------------------------------------------------------
    family = sections_payload.get("form_family") or {}
    family_value = family.get("value")
    family_conf = float(family.get("confidence", 0.0))
    family_ev = family.get("evidence", {}) if isinstance(family.get("evidence"), dict) else {}
    if family_value in (None, "unknown") or family_conf < FORM_FAMILY_LOW_CONFIDENCE:
        if family.get("provenance") != "human-confirmed":
            questions.append(_question(
                "form_family",
                [
                    {"value": "dance_form", "score": round(float(family_ev.get("dance_score", 0.0)), 4)},
                    {"value": "song_form", "score": round(float(family_ev.get("song_score", 0.0)), 4)},
                    {"value": "hybrid", "score": round(min(float(family_ev.get("dance_score", 0.0)),
                                                           float(family_ev.get("song_score", 0.0))), 4)},
                ],
                [float(s["start"]) for s in sections[:1]],
                f"inferred confidence {family_conf:.2f} < {FORM_FAMILY_LOW_CONFIDENCE}; "
                "audio evidence for dance vs song form is close",
                leverage=1.0 - family_conf + 0.5,  # whole-song fact -> high leverage
            ))

    # --- form_family / genre disagreement flag (R1a) -----------------------
    genre_labels = {str(g).lower() for g in (genre_result or {}).get("genres", [])}
    for fam, hint_genres in _FAMILY_GENRE_HINTS.items():
        if family_value == fam and genre_labels and not (genre_labels & hint_genres):
            questions.append(_question(
                "form_family_vs_genre",
                [{"value": family_value, "score": family_conf},
                 {"value": f"genre={sorted(genre_labels)}", "score": round(float((genre_result or {}).get("confidence", 0.0)), 4)}],
                [],
                f"inferred form_family '{family_value}' disagrees with the genre label {sorted(genre_labels)}; "
                "a human-confirmed genre would break the tie",
                leverage=0.6,
            ))
            break

    # --- ambiguous form_role per section ----------------------------------
    for section in sections:
        role = section.get("form_role")
        margin = section.get("form_role_margin")
        if role == "unknown" or (margin is not None and float(margin) < FORM_ROLE_THIN_MARGIN):
            questions.append(_question(
                f"sections.{section.get('section_id')}.form_role",
                [{"value": role, "score": round(float(section.get("form_role_confidence") or 0.0), 4)}],
                [float(section["start"])],
                f"best-vs-second-best role margin {float(margin or 0.0):.2f} below {FORM_ROLE_THIN_MARGIN}",
                leverage=0.4 - float(margin or 0.0),
            ))

    # --- missing drop ----------------------------------------------------
    has_drop = facts.get("has_drop")
    has_drop_value = has_drop.get("value") if isinstance(has_drop, dict) else has_drop
    detected_drops = [
        e for e in (timeline_payload or {}).get("events", [])
        if str(e.get("type")) == "drop" or e.get("composite")
    ]
    if has_drop_value and not detected_drops:
        questions.append(_question(
            "drops.timed_location",
            [{"value": "unknown", "score": 0.0}],
            [],
            "song_facts.has_drop is human-confirmed true but the pipeline detected no drop; "
            "a timed 'Drop in' hint in human_hints.json would anchor detection",
            leverage=0.9,
        ))

    questions.sort(key=lambda q: q["leverage"], reverse=True)

    payload = {
        "schema_version": "1.1",
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "genre_file": str(paths.artifact("genre.json")),
            "engine": "deterministic.review_queue.v1",
        },
        "direction_of_flow": "analyzer proposes here; a human disposes into reference/human/song_facts.json",
        "open_question_count": len(questions),
        "questions": questions,
    }
    write_json(paths.artifact("validation", "review_queue.json"), payload)
    return payload
