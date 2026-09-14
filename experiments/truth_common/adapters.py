"""Adapters translating three sibling experiments' EXISTING proposal output
into the `energy`/`tension` candidate-producer shape
`energy_tension.score_energy_tension` expects
(`[{"start", "end", "energy" | "tension"}, ...]`).

Read-only: `clap`, `texture_novelty` and `phrase_periodicity` are **not**
reworked here — nothing in their own directories changes
(docs/product-refinement-v3.6.md item 5's adapter rule). Each function names
the exact source field(s) it reads and its mapping formula; all deterministic,
none tuned to a target number.
"""
from __future__ import annotations

import json

from . import paths

# clap/character.py's four foreground `kind` labels (its shadow-allin1 labels
# carry no energy claim and are skipped) -> the operator's 1-5 energy scale.
_CHARACTER_ENERGY = {"void": 1, "breath": 2, "vocal lead": 3, "full power": 5}

# phrase_periodicity.py's `regime` -> tension. `through-composed` (rep@bar
# below threshold — no loop found, still developing) reads tenser than a
# locked loop; `half-bar-loop` (denser repetition) reads more driving than a
# slow `bar-loop`. Fixed, not tuned.
_REGIME_TENSION = {"through-composed": 4, "bar-loop": 2, "half-bar-loop": 3}


def _load_blocks(song: str, filename: str) -> list[dict]:
    path = paths.proposals_path(song, filename)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("blocks", [])


def clap_character_predicted_energy(song: str) -> list[dict]:
    """`reference/proposals/character.json` blocks: `kind` in
    `_CHARACTER_ENERGY` -> `energy` directly. Shadow-label blocks (`kind`
    starting `"shadow "`) carry no energy claim and are skipped."""
    out = []
    for b in _load_blocks(song, "character.json"):
        e = _CHARACTER_ENERGY.get(b.get("kind"))
        if e is None:
            continue
        out.append({"start": b["start_s"], "end": b["end_s"], "energy": e})
    return out


def clap_character_predicted_tension(song: str) -> list[dict]:
    """Same file, `evidence.calm_z` (CLAP's calm<->intense axis, a per-song
    z-score) -> `tension = clamp(round(3 - calm_z), 1, 5)`: `calm_z == 0`
    (song-average) -> tension 3; more calm (positive) lowers it, more intense
    (negative) raises it. Blocks with no `calm_z` (pure `stems`-source
    blocks, and shadow blocks) are skipped."""
    out = []
    for b in _load_blocks(song, "character.json"):
        calm_z = (b.get("evidence") or {}).get("calm_z")
        if calm_z is None:
            continue
        t = max(1, min(5, round(3 - calm_z)))
        out.append({"start": b["start_s"], "end": b["end_s"], "tension": int(t)})
    return out


def texture_novelty_predicted_tension(song: str) -> list[dict]:
    """`reference/proposals/texture_novelty.json` blocks: a block's own
    `edge_strength` (the novelty magnitude of the boundary that OPENS it) is
    song-relative-quintile-binned to 1-5 via
    `rhythm_energy_common.quintile_with_margin` — a strong incoming edge
    stands in for "arriving somewhere tenser". The first block (no incoming
    edge, `edge_strength: null`) is skipped."""
    from experiments.rhythm_energy_common import quintile_with_margin

    blocks = [
        b for b in _load_blocks(song, "texture_novelty.json")
        if b.get("edge_strength") is not None
    ]
    if not blocks:
        return []
    raw = [float(b["edge_strength"]) for b in blocks]
    binned = quintile_with_margin(raw)
    return [
        {"start": b["start_s"], "end": b["end_s"], "tension": int(t)}
        for b, (t, _conf) in zip(blocks, binned)
    ]


def phrase_periodicity_predicted_tension(song: str) -> list[dict]:
    """`reference/proposals/phrase_periodicity.json` blocks: `regime` ->
    `_REGIME_TENSION`. A missing/unknown regime is skipped."""
    out = []
    for b in _load_blocks(song, "phrase_periodicity.json"):
        t = _REGIME_TENSION.get(b.get("regime"))
        if t is None:
            continue
        out.append({"start": b["start_s"], "end": b["end_s"], "tension": int(t)})
    return out
