"""Anchor votes -> one downbeat phase per trusted run -> bar labels. Pure functions, no I/O.

Rules (refinement v3.12 item 3):

* Beat times are never touched. Only the bar index is relabelled.
* A bar is always 4 beats: inside a trusted run (the beats between `off_grid_spans`)
  the downbeat phase is one residue of the beat index mod 4. A phase slip would
  need a bar of another length, so it is never published; where the anchors say the
  phase slipped, the span is `resolved: false` (`downbeat_confidence` null) instead.
* ANCHORS each vote for "this beat is a downbeat":
  - kick-phase: over a sliding window of `KICK_WINDOW_BEATS` beats the phase of four
    carrying most kick attacks (item 29), when it carries `KICK_MARGIN` x the
    runner-up and >= `KICK_MIN_ATTACKS` attacks. Four-on-the-floor ties and abstains.
  - impacts (`song_event_timeline`), their physical onset on a beat.
  - bass / drums stem entries (`arrangement_state` block `entered`) on a beat.
* The run's phase is the highest summed vote. No vote -> allin1's majority phase,
  every downbeat of the run unresolved. A downbeat's `confidence` is the share of
  votes within +-`LOCAL_BEATS` beats that agree with the run phase, null when the
  share is under `AGREE_MIN` or the evidence under `EVIDENCE_MIN`.
"""
from __future__ import annotations

import bisect

BEATS_PER_BAR = 4
#: Sliding window for the kick-phase vote: 8 bars, stepped one bar.
KICK_WINDOW_BEATS = 32
KICK_STEP_BEATS = 4
#: Top phase must carry this multiple of the runner-up, and this many attacks, to vote.
KICK_MARGIN = 1.5
KICK_MIN_ATTACKS = 6
#: Weight of one kick-phase window vote (windows overlap 8x, so a single window is light).
KICK_WEIGHT = 0.25
#: An anchor must sit within this fraction of a beat of a trusted beat.
SNAP_BEAT_FRAC = 0.25
#: Weight when an arrangement block carries `confidence: null` (honest: a weak vote).
NULL_CONF_WEIGHT = 0.25
#: A downbeat's local evidence window and acceptance.
LOCAL_BEATS = 16
AGREE_MIN = 0.75
EVIDENCE_MIN = 1.0
#: A kick attack is binned like `kick_attacks.present`: its physical onset leads the beat.
ASSIGN_LEAD_S = 0.05
KICK_MIN_CONF = 0.25


def trusted_runs(trusted: list[bool]) -> list[tuple[int, int]]:
    """Inclusive (lo, hi) beat-index ranges of consecutive trusted beats."""
    runs, lo = [], None
    for i, t in enumerate(trusted):
        if t and lo is None:
            lo = i
        if not t and lo is not None:
            runs.append((lo, i - 1))
            lo = None
    if lo is not None:
        runs.append((lo, len(trusted) - 1))
    return runs


def nearest_beat(beat_times: list[float], t: float, tol: float) -> int | None:
    i = bisect.bisect_left(beat_times, t)
    cands = [j for j in (i - 1, i) if 0 <= j < len(beat_times)]
    if not cands:
        return None
    j = min(cands, key=lambda k: abs(beat_times[k] - t))
    return j if abs(beat_times[j] - t) <= tol else None


def event_votes(beat_times: list[float], trusted: list[bool], impacts: list[dict],
                entries: list[dict], beat_len: float) -> list[dict]:
    """Votes {beat_index, weight, kind} from impacts and bass/drums entries on a trusted beat."""
    out = []
    for kind, rows in (("impact", impacts), ("entry", entries)):
        for r in rows:
            j = nearest_beat(beat_times, r["t"], SNAP_BEAT_FRAC * beat_len)
            if j is None or not trusted[j]:
                continue
            c = r.get("confidence")
            out.append({"beat_index": j, "weight": float(c) if c else NULL_CONF_WEIGHT, "kind": kind})
    return out


def beat_kick_strength(beat_times: list[float], kicks: list[dict], beat_len: float) -> list[float]:
    """Summed confidence of non-echo attacks (conf >= KICK_MIN_CONF) binned onto the nearest beat."""
    s = [0.0] * len(beat_times)
    for e in kicks:
        if e["echo_of"] is not None or e["confidence"] < KICK_MIN_CONF:
            continue
        j = nearest_beat(beat_times, e["time"] + ASSIGN_LEAD_S, 0.5 * beat_len)
        if j is not None:
            s[j] += e["confidence"]
    return s


def kick_votes(strength: list[float], runs: list[tuple[int, int]]) -> list[dict]:
    """Sliding-window kick-phase votes, one stepped bar at a time, inside each trusted run."""
    out = []
    for lo, hi in runs:
        for w in range(lo, hi - KICK_WINDOW_BEATS + 2, KICK_STEP_BEATS):
            seg = strength[w:w + KICK_WINDOW_BEATS]
            if len(seg) < KICK_WINDOW_BEATS:
                continue
            per = [sum(seg[p::BEATS_PER_BAR]) for p in range(BEATS_PER_BAR)]
            n = sum(1 for x in seg if x > 0)
            order = sorted(range(BEATS_PER_BAR), key=lambda p: -per[p])
            top, second = per[order[0]], per[order[1]]
            if n < KICK_MIN_ATTACKS or top <= 0 or top < KICK_MARGIN * second:
                continue
            out.append({"beat_index": w + order[0], "weight": KICK_WEIGHT, "kind": "kick_phase",
                        "center": w + KICK_WINDOW_BEATS // 2})
    return out


def run_phase(votes: list[dict], lo: int, hi: int, fallback: dict[int, int]) -> tuple[int, str]:
    """Residue (mod 4 of the global beat index) for the run and its source."""
    sums = [0.0] * BEATS_PER_BAR
    for v in votes:
        if lo <= v["beat_index"] <= hi:
            sums[v["beat_index"] % BEATS_PER_BAR] += v["weight"]
    if max(sums) > 0:
        return max(range(BEATS_PER_BAR), key=lambda p: (sums[p], -p)), "anchors"
    cnt = [0] * BEATS_PER_BAR
    for i, one in fallback.items():
        if lo <= i <= hi and one:
            cnt[i % BEATS_PER_BAR] += 1
    return (max(range(BEATS_PER_BAR), key=lambda p: (cnt[p], -p)), "allin1") if max(cnt) else (0, "none")


def reanchor(beat_times: list[float], trusted: list[bool], allin1_down: dict[int, int],
             impacts: list[dict], entries: list[dict], kicks: list[dict], beat_len: float) -> dict:
    """Label every beat. Returns {'beats': [{bar, beat, downbeat, confidence}], 'runs': [...], 'spans': [...],
    'votes': [...]}. `allin1_down` maps beat index -> 1 where allin1 labels the beat a downbeat."""
    n = len(beat_times)
    runs = trusted_runs(trusted)
    votes = event_votes(beat_times, trusted, impacts, entries, beat_len)
    votes += kick_votes(beat_kick_strength(beat_times, kicks, beat_len), runs)

    phase = [0] * n
    run_rows = []
    prev = None
    for lo, hi in runs:
        ph, src = run_phase(votes, lo, hi, allin1_down)
        if src == "none" and prev is not None:
            ph = prev
        run_rows.append({"lo": lo, "hi": hi, "phase": ph, "source": src})
        prev = ph
    if not run_rows:  # no trusted beat at all: allin1 / zero, everything unresolved
        ph, src = run_phase([], 0, n - 1, allin1_down)
        run_rows = [{"lo": 0, "hi": n - 1, "phase": ph, "source": src}]
    # beat -> phase: a trusted beat uses its run, an untrusted one continues the previous run
    # (the first run for a leading stretch).
    r = 0
    for i in range(n):
        while r + 1 < len(run_rows) and i > run_rows[r]["hi"] and i >= run_rows[r + 1]["lo"]:
            r += 1
        phase[i] = run_rows[r]["phase"]

    down = [(i - phase[i]) % BEATS_PER_BAR == 0 for i in range(n)]
    labels = []
    bar = 0
    first_down = next((i for i in range(n) if down[i]), n)
    if first_down > 0:
        bar = 1  # leading pickup is its own partial bar
    for i in range(n):
        if down[i]:
            bar += 1
        labels.append({"bar": max(bar, 1), "beat": (i - phase[i]) % BEATS_PER_BAR + 1, "downbeat": down[i],
                       "confidence": None})

    src_of = {}
    for row in run_rows:
        for i in range(row["lo"], row["hi"] + 1):
            src_of[i] = row["source"]
    for i in range(n):
        if not down[i] or src_of.get(i) != "anchors":
            continue
        agree = disagree = 0.0
        for v in votes:
            if abs(v["beat_index"] - i) <= LOCAL_BEATS if v["kind"] != "kick_phase" else abs(v["center"] - i) <= LOCAL_BEATS:
                if v["beat_index"] % BEATS_PER_BAR == phase[i]:
                    agree += v["weight"]
                else:
                    disagree += v["weight"]
        tot = agree + disagree
        if tot >= EVIDENCE_MIN and agree / tot >= AGREE_MIN:
            labels[i]["confidence"] = round(agree / tot, 3)

    spans = []
    cur = None
    for i in range(n):
        if down[i] and labels[i]["confidence"] is None:
            if cur is None:
                cur = [i, i]
            cur[1] = i
        elif down[i] and cur is not None:
            spans.append(cur)
            cur = None
    if cur is not None:
        spans.append(cur)
    span_rows = [{"start_beat_index": a, "end_beat_index": b, "start_s": beat_times[a], "end_s": beat_times[b],
                  "resolved": False, "reason": src_of.get(a, "off_grid") if src_of.get(a) != "anchors" else "anchors_disagree"}
                 for a, b in spans]
    return {"beats": labels, "runs": run_rows, "spans": span_rows, "votes": votes}


def irregular_bars(labels: list[dict], trusted: list[bool]) -> dict:
    """Bars with != 4 beats. `strict` counts every one; `outside` skips a bar holding an untrusted beat
    (off_grid_spans) and the two song-edge partials (leading pickup, trailing remainder)."""
    bars: list[list[int]] = []
    for i, b in enumerate(labels):
        if not bars or labels[bars[-1][0]]["bar"] != b["bar"]:
            bars.append([])
        bars[-1].append(i)
    strict = [bars_i for bars_i in bars if len(bars_i) != BEATS_PER_BAR]
    outside = [bi for k, bi in enumerate(bars)
               if len(bi) != BEATS_PER_BAR and 0 < k < len(bars) - 1 and all(trusted[i] for i in bi)]
    return {"n_bars": len(bars), "strict": len(strict), "outside": len(outside),
            "outside_rows": [(b[0], len(b)) for b in outside]}
