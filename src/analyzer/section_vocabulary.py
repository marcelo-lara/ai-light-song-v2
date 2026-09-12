"""Item 10 (v3.5) — the section `function`/label vocabulary, repo-wide.

`docs/segments-vocabulary.md` replaces allin1's narrower Harmonix set
(`intro outro break bridge inst solo verse chorus`) as the source of truth for
the `function` field on every `sections.json` row — whether the row's
boundaries came from allin1 or from a hand-marked
`reference/human/segments.json`. Nothing downstream of `segmentation.py` or
`ui_data.py` should see a raw Harmonix token or an un-normalized human string.

`HARMONIX_TO_VOCABULARY` maps allin1's eight musical labels (sentinels
`start`/`end` are dropped before this stage runs — see
`segmentation.py:_phrase_rows`) onto the closest term in the vocabulary doc.
Two of the eight have no direct match:

- `inst` -> `Main` ("a primary musical section in arrangements that do not
  follow a conventional verse/chorus structure" — the vocabulary doc's own
  words for exactly this case).
- `solo` -> `Main` for the same reason: a featured solo is also an
  instrumental passage outside verse/chorus form, and the vocabulary has no
  dedicated "solo" term either.

Both `inst` and `solo` therefore display as `Main`. This is safe only because
identity (`same_label_as`) is computed by `segmentation.py` from allin1's
*raw* Harmonix token before this mapping is applied, never from the
post-mapping display string — so an `inst` run is never claimed to be "the
same label as" a later `solo` run just because both display as `Main`.
"""
from __future__ import annotations

#: allin1's Harmonix vocabulary -> the nearest `docs/segments-vocabulary.md`
#: term. Keys are exactly `segmentation.MUSICAL_LABELS` (sentinels excluded).
HARMONIX_TO_VOCABULARY: dict[str, str] = {
    "intro": "Intro",
    "outro": "Outro",
    "break": "Breakdown",
    "bridge": "Bridge",
    "inst": "Main",
    "solo": "Main",
    "verse": "Verse",
    "chorus": "Chorus",
}

#: The flat vocabulary from `docs/segments-vocabulary.md`, single-word aliases
#: split out of its "X / Y" entries (e.g. "Breakdown / Break" -> both
#: "Breakdown" and "Break" are valid canonical spellings). Used only to fix
#: casing on human-typed labels — never to reject or replace one a human
#: actually wrote.
CANONICAL_TERMS: tuple[str, ...] = (
    "Intro",
    "Outro",
    "Verse",
    "Main",
    "Pre-Chorus",
    "Chorus",
    "Post-Chorus",
    "Refrain",
    "Breakdown",
    "Break",
    "Pre-Build",
    "Build-Up",
    "Build",
    "Fill",
    "Pre-Drop",
    "Drop",
    "Extended Drop",
    "Bridge",
    "Mid-Intro",
)
_CANONICAL_BY_CASEFOLD: dict[str, str] = {term.casefold(): term for term in CANONICAL_TERMS}

#: Known non-canonical synonyms a human operator might type in
#: `reference/human/segments.json`, mapped onto the nearest real vocabulary
#: term. Checked before the pass-through-unchanged fallback in
#: `normalize_human_label` so a known synonym doesn't silently ship as an
#: out-of-vocabulary `function` value. Keys are casefolded.
#:
#: - `"instrumental"` -> `"Main"`: same target and rationale as allin1's
#:   `inst`/`solo` in `HARMONIX_TO_VOCABULARY` above — an instrumental passage
#:   outside verse/chorus form, and the vocabulary has no dedicated term for it.
_HUMAN_LABEL_ALIASES: dict[str, str] = {
    "instrumental": "Main",
}


def normalize_allin1_label(label: str | None) -> str | None:
    """Raw allin1 Harmonix token -> vocabulary term, or `None` unchanged.

    Raises on an unrecognised token rather than passing it through — allin1's
    label set is closed and versioned (`HARMONIX_LABELS`); a token outside it
    means the model version changed underneath this mapping (no silent
    fallbacks)."""
    if label is None:
        return None
    try:
        return HARMONIX_TO_VOCABULARY[label]
    except KeyError:
        raise ValueError(
            f"section_vocabulary: {label!r} is not one of allin1's Harmonix musical "
            f"labels {sorted(HARMONIX_TO_VOCABULARY)}; the model version may have changed"
        ) from None


def normalize_human_label(label: str) -> str:
    """Case/whitespace normalization, plus a small known-synonym alias table.
    Human labels in `reference/human/segments.json` are almost always already
    written in `docs/segments-vocabulary.md` terms — this fixes stray
    casing/whitespace against the canonical spelling, and additionally maps
    the handful of known non-canonical synonyms in `_HUMAN_LABEL_ALIASES`
    (e.g. "Instrumental" -> "Main") so they don't ship as out-of-vocabulary
    `function` values. A label that matches neither is passed through
    stripped, unchanged: it is the operator's own ground truth, not a guess
    this module is entitled to overwrite (no silent fallbacks cuts both
    ways)."""
    stripped = label.strip()
    casefolded = stripped.casefold()
    if casefolded in _CANONICAL_BY_CASEFOLD:
        return _CANONICAL_BY_CASEFOLD[casefolded]
    if casefolded in _HUMAN_LABEL_ALIASES:
        return _HUMAN_LABEL_ALIASES[casefolded]
    return stripped
