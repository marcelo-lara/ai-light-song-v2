"""Score against the one word-level lyric reference in the repo.

`_test_song`'s `reference/moises/lyrics.json` is the only hand-checked lyric
ground truth. That is one song — corpus-wide quality is judged by ear in the
**Vocal Transcription** lane, and this module reports only what the reference
can actually support:

- **Lyric WER** — VocalParse vs Moises, and the Whisper baseline vs Moises.
- **Word-onset median absolute error** — Whisper baseline vs Moises, the number
  every timing claim in this experiment rests on.
"""
from __future__ import annotations

import re

from . import model, whisper_baseline
from .paths import GOLD_SONGS, moises_words


def _norm(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _wer(ref: list[str], hyp: list[str]) -> float:
    # Levenshtein over word lists.
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / max(1, len(ref))


def _onset_mae(ref_words: list[dict], hyp_words: list[dict]) -> float | None:
    if not ref_words or not hyp_words:
        return None
    errs = []
    for rw in ref_words:
        cand = [hw for hw in hyp_words if _norm(hw["w"]) == _norm(rw["text"])]
        if cand:
            errs.append(min(abs(hw["t"] - rw["start"]) for hw in cand))
    if not errs:
        return None
    errs.sort()
    return errs[len(errs) // 2]


def report(songs: list[str]) -> str:
    lines = ["lyric WER / word-onset MAE against reference/moises (｜ = missing)", ""]
    lines.append(f"  {'song':<34}{'VP WER':>9}{'Whisper WER':>13}{'Whisper onset MAE':>19}")
    for song in songs:
        ref = moises_words(song)
        if not ref:
            lines.append(f"  {song:<34}{'｜':>9}{'｜':>13}{'｜':>19}")
            continue
        ref_words = _norm(" ".join(w["text"] for w in ref))

        vp_wer = wh_wer = mae = None
        if song in model.cached_songs([song]):
            vp_wer = _wer(ref_words, _norm(model.load(song).get("lyrics", "")))
        if song in whisper_baseline.cached_songs([song]):
            wh = whisper_baseline.load(song)
            wh_wer = _wer(ref_words, _norm(" ".join(l["text"] for l in wh["lines"])))
            mae = _onset_mae(ref, [w for l in wh["lines"] for w in l.get("words", [])])

        lines.append(
            f"  {song:<34}"
            f"{('%.2f' % vp_wer) if vp_wer is not None else '｜':>9}"
            f"{('%.2f' % wh_wer) if wh_wer is not None else '｜':>13}"
            f"{('%.2f s' % mae) if mae is not None else '｜':>19}"
        )
    return "\n".join(lines)


def default_songs() -> list[str]:
    return GOLD_SONGS
