"""Phase 3 (relate) — section-function energy contest.

allin1's functional labels carry a training prior that a `chorus` is the loud,
dense, climactic passage. On a Eurovision-shaped song that prior inverts: the
sung `chorus` is the *quietest* passage and the following `verse` / post-chorus
hook out-punches it (`docs/alessandra_findings.md` §1). A cue model reading
`sections.json` then lights the calmest moment in the song like a climax.

This stage does not flip the label — flipping would assert a fresh claim from a
thin heuristic, and a confident wrong answer costs the show (refinement `D5`).
It **keeps allin1's label and flags it**: a flagged row gets
`function_status: "contested"` + `contested_by: "energy"` in the published
`sections.json` (the publisher fuses; this stage only writes its own artifact —
`docs/analysis-definition.md` phase rule).

Nothing here reads audio. Inputs are the *published* top-level files
`sections.json`, `arrangement_state.json` and `loudness.json` — which is what
makes it a phase-3 stage.

Measured — `experiments/section_function_contest/measurement.md`, per-section
mean mix + per-stem RMS across all 23 analysed songs against each allin1
`function`. The "chorus quieter than the following verse" contradiction is
**not** corpus-wide: it fires on 4 sections across 2 songs (`Queen of Kings -
Alessandra` ×3, `It's a fine day - Opus III` ×1); the other 21 songs flag
nothing. So the rule ships **conservative** — a chorus is only contested when
the next section's drums are ≥ 3 dB louder AND its mix is not > 1.5 dB quieter
AND its arrangement_state stem count is not clearly thinner, and only when
allin1's own label confidence is below 0.9. On a normal song this flags nothing
and `sections.json` is byte-identical to today.
"""
from __future__ import annotations

import math

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths
from analyzer.stages.ui_data import apply_section_function_contest

#: A chorus is contested only against a following section allin1 called one of
#: these — the labels whose training prior is *lower* energy than a chorus.
HIGH_ENERGY_LABEL = "chorus"
LOWER_ENERGY_LABELS = frozenset({"verse", "bridge"})

#: The next section's drums must exceed this section's by at least this many dB.
#: Drums are the strong discriminator on the measured contradictions
#: (Queen of Kings section-002 → +17 dB, section-004 → +6.7 dB,
#: section-006 → +4.2 dB; It's a fine day section-002 → +5.0 dB).
DRUMS_MARGIN_DB = 3.0

#: Guard: the chorus mix must not be *much* louder than the next section's — a
#: chorus that is genuinely the louder passage in the mix is not "quieter".
MIX_MIN_GAP_DB = -1.5

#: Guard: the next section must not be clearly thinner in arrangement_state's
#: stem count (`next_playing - this_playing >= -1`). This is deliberately loose:
#: arrangement_state's stem count sits at its own label noise floor
#: (`arrangement_state.py` docstring), so it only vetoes a clearly-thickening
#: chorus, never drives a flag on its own.
PLAY_TOLERANCE = -1

#: A near-certain allin1 label is left alone — the energy heuristic is too thin
#: to contest it. Every measured contradiction sits at function_confidence
#: 0.54–0.74; allin1's confidently-labelled choruses (0.85+) are not touched.
FUNCTION_CONFIDENCE_CEILING = 0.9


def _db(x: float) -> float:
    return 20.0 * math.log10(max(x, 1e-9))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _section_energy(paths: SongPaths) -> list[dict]:
    """Per published-section mean mix RMS, mean drums RMS, and the
    arrangement_state playing-stem count at the section midpoint."""
    loudness = read_json(paths.loudness_output_path)
    order: list[str] = loudness["metadata"]["source_order"]
    mix_i = order.index("mix")
    drums_i = order.index("drums")
    frames = loudness["frames"]

    arr = read_json(paths.arrangement_state_output_path)
    arr_blocks = arr.get("blocks", [])

    def playing_at(t: float) -> int | None:
        block = None
        for b in arr_blocks:
            if b["start_s"] <= t < b["end_s"]:
                block = b
        if block is None and arr_blocks:
            block = arr_blocks[-1] if t >= arr_blocks[-1]["start_s"] else arr_blocks[0]
        return len(block["playing"]) if block else None

    sections = read_json(paths.sections_output_path)["sections"]
    out: list[dict] = []
    for section in sections:
        start = float(section["start"])
        end = float(section["end"])
        window = [f for f in frames if start <= f["time"] < end]
        if not window:
            continue
        out.append(
            {
                "section_id": section["section_id"],
                "function": section.get("function"),
                "function_confidence": section.get("function_confidence"),
                "mix_rms": _mean([f["values"][mix_i] for f in window]),
                "drums_rms": _mean([f["values"][drums_i] for f in window]),
                "playing": playing_at((start + end) / 2.0),
            }
        )
    return out


def _contest(sections: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for i, cur in enumerate(sections):
        nxt = sections[i + 1] if i + 1 < len(sections) else None
        contested = False
        margin: float | None = None
        if nxt is not None:
            drums_gap_db = _db(nxt["drums_rms"]) - _db(cur["drums_rms"])
            mix_gap_db = _db(nxt["mix_rms"]) - _db(cur["mix_rms"])
            play_gap = (
                (nxt["playing"] - cur["playing"])
                if (nxt["playing"] is not None and cur["playing"] is not None)
                else 0
            )
            margin = round(drums_gap_db, 2)
            fconf = cur.get("function_confidence")
            contested = (
                cur.get("function") == HIGH_ENERGY_LABEL
                and nxt.get("function") in LOWER_ENERGY_LABELS
                and (fconf is None or float(fconf) <= FUNCTION_CONFIDENCE_CEILING)
                and drums_gap_db >= DRUMS_MARGIN_DB
                and mix_gap_db >= MIX_MIN_GAP_DB
                and play_gap >= PLAY_TOLERANCE
            )
        rows.append(
            {
                "section_id": cur["section_id"],
                "function": cur.get("function"),
                "contested": contested,
                "contested_by": "energy" if contested else None,
                "margin": margin,
            }
        )
    return rows


def contest_section_function(paths: SongPaths) -> dict:
    """Stage entry point. Writes `artifacts/section_function_contest.json`, then
    re-fuses the published `sections.json` through the publisher so flagged rows
    carry `function_status: "contested"` + `contested_by: "energy"` (unflagged
    rows stay byte-identical to `build-ui-data`'s output)."""
    energy = _section_energy(paths)
    contest_rows = _contest(energy)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_from": {
            "engine": "analyzer.stages.section_function",
            "reads": ["sections.json", "arrangement_state.json", "loudness.json"],
            "drums_margin_db": DRUMS_MARGIN_DB,
            "mix_min_gap_db": MIX_MIN_GAP_DB,
            "play_tolerance": PLAY_TOLERANCE,
            "function_confidence_ceiling": FUNCTION_CONFIDENCE_CEILING,
        },
        "sections": contest_rows,
    }
    write_json(paths.artifact("section_function_contest.json"), payload)
    apply_section_function_contest(paths)
    return payload
