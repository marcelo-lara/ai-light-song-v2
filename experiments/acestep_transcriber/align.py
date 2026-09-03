"""Put ACE-Step's lyric lines and section tags on a clock.

The transcriber emits ordered lines and `[Section]` tags but not reliable
seconds. Same rule as the VocalParse experiment (constitution §2): borrow the
Whisper baseline's word timeline, and where the two transcripts disagree, refuse
to invent timing.

- Match ACE-Step lines to Whisper lines by normalised-text similarity in order
  (monotonic alignment). Each matched ACE-Step line takes its Whisper line's
  span.
- A `[Section]` span runs from its first placed line to the last line before the
  next tag.
- If fewer than half the ACE-Step lines match a Whisper line, mark the whole
  result `alignment: "unavailable"` and place lines evenly across the sung
  region with `approx: true` — flagged, never presented as measured.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def _match(ace_lines: list[str], whisper_lines: list[dict]) -> list[dict | None]:
    """Monotonic best-match of each ace line to a whisper line span."""
    out: list[dict | None] = []
    wi = 0
    for al in ace_lines:
        an = _norm(al)
        best, best_j = 0.0, None
        for j in range(wi, len(whisper_lines)):
            r = SequenceMatcher(None, an, _norm(whisper_lines[j]["text"])).ratio()
            if r > best:
                best, best_j = r, j
        if best_j is not None and best >= 0.4:
            out.append(whisper_lines[best_j])
            wi = best_j + 1
        else:
            out.append(None)
    return out


def align(parsed: dict, whisper_lines: list[dict]) -> dict:
    sections = parsed.get("sections", [])
    flat = [(si, li, ln) for si, s in enumerate(sections)
            for li, ln in enumerate(s.get("lines", []))]
    ace_lines = [ln for _, _, ln in flat]

    if not ace_lines or not whisper_lines:
        return {"alignment": "unavailable", "reason": "nothing to align",
                "lines": [], "sections": []}

    matched = _match(ace_lines, whisper_lines)
    hit = sum(m is not None for m in matched)

    lines_out = []
    if hit >= max(1, len(ace_lines) // 2):
        alignment, reason = "words", f"{hit}/{len(ace_lines)} lines matched to whisper"
        for (si, li, ln), m in zip(flat, matched):
            if m is None:
                continue
            lines_out.append({
                "id": f"ace{len(lines_out) + 1:03d}", "section_index": si,
                "start_s": round(m["start_s"], 3), "end_s": round(m["end_s"], 3),
                "text": ln, "words": [], "confidence": None,
            })
    else:
        alignment = "unavailable"
        reason = f"only {hit}/{len(ace_lines)} lines matched — timing is approximate"
        t0 = whisper_lines[0]["start_s"]
        step = (whisper_lines[-1]["end_s"] - t0) / max(1, len(ace_lines))
        for k, (si, li, ln) in enumerate(flat):
            lines_out.append({
                "id": f"ace{k + 1:03d}", "section_index": si,
                "start_s": round(t0 + k * step, 3), "end_s": round(t0 + (k + 1) * step, 3),
                "text": ln, "words": [], "confidence": None, "approx": True,
            })

    # Every `[tag]` becomes a span, including the line-less ones ([Intro],
    # [Drop 1], [Instrumental], the descriptive scene tags) — they carry no
    # lyric but they are exactly the structural cues this repo is after. A
    # line-less tag is placed in the gap between its lined neighbours.
    song_start = whisper_lines[0]["start_s"]
    song_end = whisper_lines[-1]["end_s"]
    lined = {si: [l for l in lines_out if l["section_index"] == si]
             for si in range(len(sections))}

    section_spans = []
    for si, s in enumerate(sections):
        mine = lined.get(si) or []
        if mine:
            start_s, end_s = mine[0]["start_s"], mine[-1]["end_s"]
        else:
            prev_end = next((lined[j][-1]["end_s"] for j in range(si - 1, -1, -1)
                             if lined.get(j)), song_start)
            next_start = next((lined[j][0]["start_s"] for j in range(si + 1, len(sections))
                               if lined.get(j)), song_end)
            start_s = end_s = round((prev_end + next_start) / 2, 3)
        section_spans.append({
            "id": f"aces{si + 1:03d}", "tag": s["tag"], "instruments": s.get("instruments"),
            "start_s": start_s, "end_s": end_s, "line_count": len(mine),
            "approx": not mine or alignment == "unavailable",
        })

    return {"alignment": alignment, "reason": reason,
            "lines": lines_out, "sections": section_spans}
