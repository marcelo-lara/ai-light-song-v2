"""Phrase edges -> downbeat anchors -> bars counted in fours. Pure functions, no I/O.

Rules (refinement v3.10 item 10), all local, no song-wide grid:

* An ANCHOR is a phrase start edge that is a downbeat: it has no `conflicts`, it
  sits on a trusted beat (`snapped`), its evidence includes a stem/presence
  ENTRY or an impact (exits and gap/riser/roll ends alone are not downbeats),
  and its summed evidence `score` >= `ANCHOR_MIN_SCORE`.
* Between consecutive anchors a and b (beat indices) bars are counted in fours
  on the beat list: downbeats at a, a+4, a+8 ... If (b - a) % 4 != 0 the two
  anchors disagree on the phase and the span is `resolved: false`, no downbeat
  is emitted inside it. A span that crosses an untrusted (off-grid) beat is
  `resolved: false` too — a beat count over a stretch where the tracker lost the
  grid is not evidence.
* An anchor reaches `REACH_BEATS` beats past the outermost anchors (counting in
  fours through trusted beats only). allin1's downbeat phase is used only on
  beats no anchor reaches; inside an unresolved span nothing is emitted.
"""
from __future__ import annotations

import bisect

#: Phrases accepts an edge at summed evidence >= 1.5 (its own ACCEPT_SCORE), so
#: 1.5 adds no extra filter: every conflict-free snapped entry/impact edge counts.
#: Chosen BEFORE scoring; the sensitivity row at 2.5 in the README is labelled as such.
ANCHOR_MIN_SCORE = 1.5
#: Beats an anchor reaches before the first / after the last anchor: 16 bars.
REACH_BEATS = 64
#: An anchor edge time must be within this many seconds of a beat time.
SNAP_TOL_S = 0.05
BEATS_PER_BAR = 4

ENTRY_KINDS = ("stem_enter", "presence_enter", "impact")


def anchor_edges(phrases: list[dict], min_score: float = ANCHOR_MIN_SCORE) -> list[dict]:
    """Start edges of `phrases[1:]` that qualify as downbeat anchors."""
    out = []
    for p in phrases[1:]:
        e = p.get("start_edge")
        if not e or e.get("conflicts") or not e.get("snapped"):
            continue
        if e.get("score", 0.0) < min_score:
            continue
        if not any(k.split(":")[0] in ENTRY_KINDS for k in e.get("kinds", [])):
            continue
        out.append({"t": float(e["t"]), "score": float(e["score"]), "kinds": list(e["kinds"]),
                    "confidence": p.get("confidence")})
    return out


def locate(beat_times: list[float], anchors: list[dict], tol: float = SNAP_TOL_S) -> list[dict]:
    """Attach `beat_index` (nearest beat within `tol`); drop anchors with none; dedupe by index."""
    seen: dict[int, dict] = {}
    for a in anchors:
        i = bisect.bisect_left(beat_times, a["t"])
        cands = [j for j in (i - 1, i) if 0 <= j < len(beat_times)]
        if not cands:
            continue
        j = min(cands, key=lambda k: abs(beat_times[k] - a["t"]))
        if abs(beat_times[j] - a["t"]) > tol:
            continue
        if j not in seen or a["score"] > seen[j]["score"]:
            seen[j] = {**a, "beat_index": j}
    return [seen[j] for j in sorted(seen)]


def count(beat_times: list[float], trusted: list[bool], anchors: list[dict],
          fallback: set[int], reach: int = REACH_BEATS) -> dict:
    """Return {'downbeats': [{beat_index, time, source}], 'spans': [...]}.

    `anchors` carry `beat_index`; `fallback` = indices where allin1 asserts a
    downbeat with a non-null confidence."""
    n = len(beat_times)
    down: dict[int, dict] = {}
    covered = [False] * n          # reached by an anchor (resolved or not)
    spans: list[dict] = []

    def put(i: int, source: str, span: int | None):
        down[i] = {"beat_index": i, "time": beat_times[i], "source": source, "span": span}

    for a in anchors:
        put(a["beat_index"], "anchor", None)
        covered[a["beat_index"]] = True

    def span_row(lo, hi, resolved, reason):
        spans.append({"start_beat_index": lo, "end_beat_index": hi,
                      "start_s": beat_times[lo], "end_s": beat_times[hi],
                      "resolved": resolved, "reason": reason})

    for a, b in zip(anchors, anchors[1:]):
        lo, hi = a["beat_index"], b["beat_index"]
        for i in range(lo, hi + 1):
            covered[i] = True
        if not all(trusted[lo:hi + 1]):
            span_row(lo, hi, False, "off_grid")
        elif (hi - lo) % BEATS_PER_BAR:
            span_row(lo, hi, False, "phase_disagree")
        else:
            span_row(lo, hi, True, None)
            sid = len(spans) - 1
            for i in range(lo + BEATS_PER_BAR, hi, BEATS_PER_BAR):
                put(i, "counted", sid)

    if anchors:
        first, last = anchors[0]["beat_index"], anchors[-1]["beat_index"]
        for start, step, stop in ((first, -1, max(first - reach, 0) - 1),
                                  (last, 1, min(last + reach, n - 1) + 1)):
            i = start
            while i != stop and 0 <= i < n:
                if not trusted[i]:
                    break
                covered[i] = True
                if (i - start) % BEATS_PER_BAR == 0 and i != start:
                    put(i, "counted_edge", None)
                i += step

    for i in sorted(fallback):
        if not covered[i]:
            put(i, "allin1", None)

    return {"downbeats": [down[i] for i in sorted(down)], "spans": spans}
