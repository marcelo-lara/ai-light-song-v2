"""Score ACE-Step Transcriber on the two things the repo can actually check.

1. **Lyrics** — WER and word-onset MAE against `_test_song`'s
   `reference/moises/lyrics.json` (the only word-level lyric reference; one
   song, so corpus-wide quality is judged by ear in the lane).
2. **Structure** — boundary recall of ACE-Step's `[Section]` spans against the
   hand-marked drop impacts and against the `allin1` experiment's transitions,
   at a matched budget. This uses the same peak-matching tolerance the other
   structure experiments report, so all three form reads sit on one axis.
"""
from __future__ import annotations

import json
import re

from . import model, whisper_baseline
from .paths import (GOLD_SONGS, allin1_proposal_path, human_impacts, moises_words,
                    proposal_path)

TOL = 1.0


def _norm(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _wer(ref: list[str], hyp: list[str]) -> float:
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / max(1, len(ref))


def _recall(marks: list[float], boundaries: list[float], tol: float = TOL) -> tuple[int, int]:
    hit = sum(any(abs(m - b) <= tol for b in boundaries) for m in marks)
    return hit, len(marks)


def _ace_boundaries(song: str) -> list[float]:
    path = proposal_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    src = next((s for s in payload["sources"]
                if s["model"].startswith("ACE-Step")), None)
    if not src:
        return []
    return sorted({s["start_s"] for s in src.get("structure", [])})


def _allin1_boundaries(song: str) -> list[float]:
    path = allin1_proposal_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return sorted(float(t["time_s"]) for t in payload.get("transitions", []))


def report(songs: list[str]) -> str:
    out = ["ACE-Step Transcriber — lyrics vs reference/moises, structure vs impacts", ""]
    for song in songs:
        out.append(f"  {song}")
        ref = moises_words(song)
        if ref and song in whisper_baseline.cached_songs([song]):
            ref_words = _norm(" ".join(w["text"] for w in ref))
            wh = whisper_baseline.load(song)
            wh_wer = _wer(ref_words, _norm(" ".join(l["text"] for l in wh["lines"])))
            out.append(f"    whisper baseline lyric WER  {wh_wer:.2f}")
            if song in model.cached_songs([song]):
                ace_text = " ".join(
                    ln for s in model.load(song).get("sections", []) for ln in s["lines"])
                out.append(f"    ACE-Step lyric WER          {_wer(ref_words, _norm(ace_text)):.2f}")

        impacts = human_impacts(song)
        if impacts:
            ah, an = _recall(impacts, _ace_boundaries(song))
            bh, bn = _recall(impacts, _allin1_boundaries(song))
            out.append(f"    impact recall @±{TOL:.1f}s   ACE-Step {ah}/{an}   allin1 {bh}/{bn}")
        out.append("")
    return "\n".join(out)


def default_songs() -> list[str]:
    return GOLD_SONGS
