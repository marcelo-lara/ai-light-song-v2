"""Put VocalParse's syllables on a clock.

VocalParse emits no timestamps. The honest options are (a) forced alignment of
its text to the vocal stem, or (b) borrowing the Whisper baseline's word
timeline. We take (b): it needs no extra model, and where VocalParse and Whisper
disagree — a different language, or garbage — that disagreement is exactly the
signal that the timing cannot be trusted.

Rule (constitution §2 — no silent fallbacks):

- If VocalParse's lyric text and Whisper's transcript overlap enough
  (character-level similarity over the shared script), distribute VocalParse's
  syllables across the matched Whisper words by sequence position and group them
  into lines on the Whisper line breaks.
- Otherwise emit one block spanning the sung region with
  `alignment: "unavailable"` and no per-word times. Never invent onsets.
"""
from __future__ import annotations

from difflib import SequenceMatcher

SIM_THRESHOLD = 0.35


def _similarity(a: str, b: str) -> float:
    a = "".join(ch.lower() for ch in a if ch.isalnum())
    b = "".join(ch.lower() for ch in b if ch.isalnum())
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def align(parsed: dict, whisper_lines: list[dict]) -> dict:
    """-> {alignment: "words"|"span"|"unavailable", lines:[...]}."""
    syllables = parsed.get("syllables", [])
    vp_text = parsed.get("lyrics", "")
    wh_text = " ".join(l["text"] for l in whisper_lines)

    sung_start = whisper_lines[0]["start_s"] if whisper_lines else 0.0
    sung_end = whisper_lines[-1]["end_s"] if whisper_lines else 0.0
    sim = _similarity(vp_text, wh_text)

    # No usable melody (the interleaved span collapsed) or no baseline to align
    # to: still surface the lyric text as one span so the lane shows what
    # VocalParse actually produced — never with per-word times.
    if not syllables or not whisper_lines or sim < SIM_THRESHOLD:
        reason = (
            "melody span empty/degenerate" if not syllables
            else "no whisper baseline" if not whisper_lines
            else f"text similarity {sim:.2f} < {SIM_THRESHOLD} "
                 "(likely language mismatch — VocalParse is Mandarin-biased)"
        )
        if not vp_text:
            return {"alignment": "unavailable", "reason": reason, "lines": []}
        return {
            "alignment": "span",
            "reason": reason,
            "lines": [{
                "id": "vp001", "start_s": round(sung_start, 3), "end_s": round(sung_end, 3),
                "text": vp_text, "words": [], "confidence": None,
                "melody": [{"midi": s["midi"], "note_value": s["note_value"]}
                           for s in syllables if s["midi"] is not None],
            }],
        }

    if False:
        return {
            "alignment": "span",
            "reason": f"text similarity {sim:.2f} < {SIM_THRESHOLD} "
                      f"(likely language mismatch — VocalParse is Mandarin-biased)",
            "lines": [{
                "id": "vp001", "start_s": round(sung_start, 3), "end_s": round(sung_end, 3),
                "text": vp_text, "words": [], "confidence": None,
                "melody": [{"midi": s["midi"], "note_value": s["note_value"]}
                           for s in syllables if s["midi"] is not None],
            }],
        }

    # Similar enough: spread syllables over the whisper word grid by position.
    words = [w for l in whisper_lines for w in l.get("words", [])]
    lines_out = []
    n = len(syllables)
    for li, wline in enumerate(whisper_lines):
        wl_words = wline.get("words", [])
        if not wl_words:
            continue
        i0 = round(n * words.index(wl_words[0]) / max(1, len(words)))
        i1 = round(n * (words.index(wl_words[-1]) + 1) / max(1, len(words)))
        chunk = syllables[i0:i1] or syllables[i0:i0 + 1]
        span = wline["end_s"] - wline["start_s"]
        melody = []
        for k, syl in enumerate(chunk):
            t = wline["start_s"] + span * k / max(1, len(chunk))
            melody.append({"t": round(t, 3), "midi": syl["midi"],
                           "note_value": syl["note_value"]})
        lines_out.append({
            "id": f"vp{li + 1:03d}",
            "start_s": round(wline["start_s"], 3),
            "end_s": round(wline["end_s"], 3),
            "text": "".join(s["text"] for s in chunk).strip(),
            "words": [],
            "confidence": round(sim, 3),
            "melody": melody,
        })
    return {"alignment": "words", "reason": f"text similarity {sim:.2f}", "lines": lines_out}
