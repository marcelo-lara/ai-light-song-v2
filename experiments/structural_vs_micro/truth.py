"""Operator-truth `kind` for a hand-marked block.

The operator does not label `structural` vs `micro` explicitly, but the intent is
legible from the block's title and length:

  * **micro** — a cue that lives *inside* a phrase: a pre-drop, a near-silence, a
    micro break, a 'hey', the sub-bar gesture phases (tension / impact /
    release), a one-off drum hit, a "spacer".
  * **structural** — a passage: an intro / verse / chorus / bridge / outro, a
    drop approach or build, a sustained vocal or synth phrase, a "breath" block.

Resolution order (documented in the README, hand-checked against the five songs'
actual hint lists):

  1. a title matching `MICRO_TITLE` -> micro; a title matching `STRUCTURAL_TITLE`
     -> structural;
  2. otherwise fall back to duration: < 1 bar -> micro, else structural.

Step 2 is what the cheap baseline does for *every* block, so the keyword layer is
the only thing that can make the phrase-grid predictor and the baseline differ on
a block whose length disagrees with its role (e.g. `Titanium`'s 3.2 s "drop
tension", which is a micro gesture in a structural-length window).
"""
from __future__ import annotations

MICRO_TITLE = (
    "micro",
    "pre-drop",
    "pre drop",
    "predrop",
    "tension",
    "impact",
    "release",
    "'hey'",
    "hey phrase",
    "spacer",
    "drum hit",
    "prepare for end",
    "verse should start",
)

STRUCTURAL_TITLE = (
    "intro",
    "verse",
    "chorus",
    "bridge",
    "outro",
    "drop approach",
    "drop build",
    "breath",
    "high energy",
    "finale",
    "synth pad",
    "post-intro",
    "vocal phrase",
)


def truth_kind(title: str, start_s: float, end_s: float, bar_len: float) -> str:
    t = (title or "").strip().lower()
    for kw in MICRO_TITLE:
        if kw in t:
            return "micro"
    for kw in STRUCTURAL_TITLE:
        if kw in t:
            return "structural"
    if bar_len <= 0:
        return "micro"
    return "micro" if (end_s - start_s) < bar_len else "structural"
