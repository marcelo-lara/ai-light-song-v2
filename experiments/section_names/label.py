"""Phrases -> build->drop units -> stage names. Pure functions, no I/O (unit-tested).

Order of work (docs/segments-vocabulary.md "Typical EDM Sequence"):

1. **Drops first.** A phrase start is a drop when a kick or bass ENTRY (the stem's
   presence over the next ENTRY_BEATS beats vs. the ENTRY_BEATS before it, silent
   beats ignored) coincides with a HIT (a gestures `impact` within HIT_BEATS beats,
   or the end of a near-silent gap). Never rising drum density: a half-time
   (dubstep) drop has fewer hits, not more. A drop with no build is found the
   same way. The run continues while kick or bass stays present; a short
   groove-off phrase that the groove returns from is a `Drop Break`.
2. **Everything else by position.** Before a drop: a Fill (snare roll / riser /
   reverse cymbal / vocal pickup ending where the gap starts), a Pre-Drop
   (near-silence across all stems), a Build-Up (consecutive phrases with riser /
   roll / opening-sweep / kick-dropout evidence), a Pre-Build (the phrase before
   it). Before the first unit: Intro; after a drop: Breakdown; after the last
   drop: Outro. A repeat of a drop inherits its label. A Fill can close any phrase.
3. **Hint = prior only** (`prior_from_hint`): moves the drop-acceptance threshold,
   the build cap and the early-drop rule. No hint -> the same run with defaults.
4. A song with no unit keeps its current labels (`status: kept_current`).

Every constant below was set a priori from the vocabulary doc; README discloses
which were looked at against labels.
"""
from __future__ import annotations

import bisect

import numpy as np

# --- drop evidence -------------------------------------------------------
ENTRY_BEATS = 8              # window either side of a candidate drop start
ENTRY_AFTER_MIN = 0.6        # the stem must be on for >= this fraction after
ENTRY_FULL_DELTA = 0.5       # after - before >= this = full entry strength
HIT_BEATS = 2.0              # an impact this close to the phrase start is the hit
HIT_SILENCE_CONF = 0.8       # a near-silent gap ending at the start is a hit
DROP_ACCEPT = 0.45           # entry x .5 + hit x .5 (x edge confidence) must reach this
REPEAT_ACCEPT_DROP = 0.15    # a phrase that repeats a drop's phrase needs this much less
EARLY_DROP_S = 20.0          # a drop before this needs EARLY_PENALTY more, unless a radio edit
EARLY_PENALTY = 0.15
MIN_DROP_BEATS = 8           # a run shorter than this is not a drop
MIN_LEAD_BEATS = ENTRY_BEATS  # a drop needs a full entry window of song before it
GROOVE_ON = 0.5              # phrase kick or bass presence at or above = groove on
SUNG_VOCALS = 0.5            # a drop run whose first phrase has this vocals presence is a Chorus
DROPBREAK_MAX_BEATS = 32     # a groove-off phrase this short, groove returning = Drop Break
POSTCHORUS_MAX_BEATS = 16    # last phrase of a run: bass on, kick off, this short = Post-Chorus
OUTRO_CAP_BEATS = 128        # an Outro is at most this long (32 bars of 4/4); earlier trailing phrases are not Outro
OUTRO_MAX_BEATS = 24         # last phrase of the song after a drop run: bass off, this short = Outro

# --- before the drop -----------------------------------------------------
BUILD_CAP_BEATS = 64         # a Build-Up reaches back at most this far (16 bars of 4/4)
PREBUILD_MAX_BEATS = 48
PREDROP_MAX_BEATS = 8        # a silent gap longer than this is a breakdown, not a Pre-Drop
GAP_END_TOL = (2.0, 1.0)     # silence may end this many beats before / after the drop start
FILL_MAX_BEATS = 8           # a Fill before a drop is at most 2 bars
FILL_END_TOL = (2.0, 1.0)    # a fill signal ends this many beats before / after the gap start
CLOSE_FILL_MAX_BEATS = 4
CLOSE_FILL_MIN_SPAN_BEATS = 2.0
CLOSE_FILL_MIN_PHRASE_BEATS = 12
CLOSE_FILL_TOL_BEATS = 1.0
SNAP_MAX_BEATS = 1.0
BUILD_ROLL = 0.15
BUILD_RISER = 0.05

# confidence position factors (positional labels are inferences from the unit)
POS_FACTOR = {"Intro": 0.9, "Main": 0.7, "Breakdown": 0.9, "Pre-Build": 0.8, "Outro": 0.9,
              "Post-Chorus": 0.7, "Drop Break": 0.7}

DROP_EXPECTED = {"trance", "big_room", "dubstep", "drum_and_bass"}
NO_DROP_EXPECTED = {"house", "techno"}


def prior_from_hint(hint: dict | None) -> dict:
    """The structure hint as a prior only. Every field a default when absent."""
    p = {"used": False, "delta": 0.0, "build_cap_beats": BUILD_CAP_BEATS, "radio_edit": False,
         "second_wave": False, "expect_no_drop": False, "sung_is_chorus": True, "notes": []}
    if not hint:
        return p
    p["used"] = True
    sub = (hint.get("genre") or {}).get("subgenre")
    ver = (hint.get("track") or {}).get("version")
    shape = hint.get("shape") or {}
    if sub in DROP_EXPECTED:
        p["delta"] -= 0.05
        p["notes"].append(f"subgenre {sub}: drops expected, acceptance -0.05")
    if sub in NO_DROP_EXPECTED:
        p["delta"] += 0.15
        p["expect_no_drop"] = True
        p["notes"].append(f"subgenre {sub}: no drop expected, acceptance +0.15")
    if sub == "big_room":
        p["second_wave"] = True
        p["notes"].append("big_room: two build->drop waves expected, a second is searched at a lower threshold")
    if sub == "trance":
        p["build_cap_beats"] = 2 * BUILD_CAP_BEATS
        p["notes"].append("trance: long builds, build cap doubled")
    if ver == "radio_edit":
        p["radio_edit"] = True
        p["notes"].append("radio edit: an early drop is normal")
    drops = shape.get("drops")
    if isinstance(drops, int) and drops == 0:
        p["delta"] += 0.15
        p["expect_no_drop"] = True
        p["notes"].append("shape.drops == 0: no drop expected, acceptance +0.15")
    if isinstance(drops, int) and drops >= 2:
        p["second_wave"] = True
        p["notes"].append(f"shape.drops == {drops}: a second wave is searched at a lower threshold")
    if shape.get("chorus_is_drop") is False:
        p["sung_is_chorus"] = False
        p["notes"].append("shape.chorus_is_drop false: a sung drop run stays Drop")
    return p


class Ctx:
    """Per-song arrays derived once from the cache."""

    def __init__(self, cache: dict):
        self.beats = np.array(cache["beats"], dtype=float)
        self.trusted = np.array(cache["trusted"], dtype=bool)
        self.bl = float(cache["beat_len"])
        self.duration = float(cache["duration"])
        self.centers = self.beats + self.bl / 2.0
        s = {k: np.array([np.nan if x is None else x for x in v], dtype=float)
             for k, v in cache["series"].items()}

        def p95(a):
            a = a[~np.isnan(a)]
            return float(np.percentile(a, 95)) if len(a) else 0.0

        kick_thr = max(0.2, 0.5 * p95(s["kick_low"]))
        bass_thr = 0.35 * p95(s["bass"])
        self.on = {
            "kick": np.where(np.isnan(s["kick_low"]), np.nan, (s["kick_low"] >= kick_thr).astype(float)),
            "bass": np.where(np.isnan(s["bass"]), np.nan, (s["bass"] >= bass_thr).astype(float)),
        }
        self.silences = cache["silences"]
        self.impacts = cache["impacts"]
        self.vocal_phrases = cache["vocal_phrases"]
        prim = cache["primitives"]
        self.rolls = prim["snare_roll"]
        self.risers = prim["riser"] + prim["reverse_cymbal"]
        self.silent_beat = np.array(
            [any(r["start"] <= c <= r["end"] for r in self.silences) for c in self.centers], dtype=bool)

    def frac(self, stem: str, lo: float, hi: float, skip_silent: bool = True) -> float | None:
        m = (self.centers >= lo) & (self.centers < hi) & ~np.isnan(self.on[stem])
        if skip_silent:
            m &= ~self.silent_beat
        return float(self.on[stem][m].mean()) if m.any() else None

    def snap(self, t: float) -> tuple[float, bool]:
        """Nearest TRUSTED beat within SNAP_MAX_BEATS, else the physical time, unsnapped."""
        tb = self.beats[self.trusted]
        if len(tb) == 0:
            return round(t, 3), False
        j = int(np.argmin(np.abs(tb - t)))
        if abs(tb[j] - t) <= SNAP_MAX_BEATS * self.bl:
            return round(float(tb[j]), 3), True
        return round(t, 3), False


def entry_and_hit(ctx: Ctx, s: float) -> dict:
    """Kick/bass entry at `s` and the hit that coincides with it, each 0..1."""
    w = ENTRY_BEATS * ctx.bl
    best, stem_used = 0.0, None
    for stem in ("kick", "bass"):
        after = ctx.frac(stem, s, s + w)
        if after is None or after < ENTRY_AFTER_MIN:
            continue
        before = ctx.frac(stem, s - w, s)
        delta = after - (before if before is not None else 0.0)
        strength = float(np.clip(delta / ENTRY_FULL_DELTA, 0.0, 1.0))
        if strength > best:
            best, stem_used = strength, stem
    hit, hit_kind = 0.0, None
    for im in ctx.impacts:
        if abs(im["start"] - s) <= HIT_BEATS * ctx.bl and im["conf"] > hit:
            hit, hit_kind = float(im["conf"]), "impact"
    for r in ctx.silences:
        if s - GAP_END_TOL[0] * ctx.bl <= r["end"] <= s + GAP_END_TOL[1] * ctx.bl and HIT_SILENCE_CONF > hit:
            hit, hit_kind = HIT_SILENCE_CONF, "gap_end"
    return {"entry": round(best, 4), "entry_stem": stem_used, "hit": round(hit, 4), "hit_kind": hit_kind}


def groove_on(p: dict) -> bool:
    return (p.get("kick_presence") or 0.0) >= GROOVE_ON or (p.get("bass_presence") or 0.0) >= GROOVE_ON


def build_like(p: dict) -> list[str]:
    """Evidence kinds that make a phrase part of a build (never drum density)."""
    ev = []
    if (p.get("snare_roll_density") or 0) >= BUILD_ROLL:
        ev.append("snare_roll")
    if (p.get("riser_density") or 0) >= BUILD_RISER:
        ev.append("riser")
    if any(s.get("direction") == "opening" for s in (p.get("filter_sweeps") or [])):
        ev.append("opening_sweep")
    if p.get("noise_sweep"):
        ev.append("noise_sweep")
    if p.get("kick_dropout_near_end"):
        ev.append("kick_dropout")
    if p.get("ends_on_gap"):
        ev.append("ends_on_gap")
    return ev


def find_runs(ctx: Ctx, phrases: list[dict], prior: dict, threshold_delta: float = 0.0) -> list[dict]:
    """Drop runs, scanned in time. A run = [first, last] phrase indices."""
    runs: list[dict] = []
    n = len(phrases)
    ids = {p["id"]: k for k, p in enumerate(phrases)}
    i = 1
    run_of: dict[str, int] = {}  # phrase id -> run index (for repeat acceptance)
    while i < n:
        p = phrases[i]
        s = p["start_s"]
        ev = entry_and_hit(ctx, s)
        edge_conf = p.get("confidence")
        factor = 0.7 + 0.3 * (edge_conf if edge_conf is not None else 1.0)
        conf = (0.5 * ev["entry"] + 0.5 * ev["hit"]) * factor
        thr = DROP_ACCEPT + prior["delta"] + threshold_delta
        if s < MIN_LEAD_BEATS * ctx.bl:
            i += 1
            continue
        if s < EARLY_DROP_S and not prior["radio_edit"]:
            thr += EARLY_PENALTY
        via_repeat = p.get("repeat_of") in run_of
        if via_repeat:
            thr -= REPEAT_ACCEPT_DROP
        if not (ev["entry"] > 0 and ev["hit"] > 0 and groove_on(p) and conf >= thr):
            i += 1
            continue
        # extend the run
        j = i
        breaks: list[int] = []
        while j + 1 < n:
            q = phrases[j + 1]
            if groove_on(q):
                j += 1
                continue
            ret = phrases[j + 2] if j + 2 < n else None
            if (q["n_beats"] <= DROPBREAK_MAX_BEATS and ret is not None and groove_on(ret)
                    and entry_and_hit(ctx, ret["start_s"])["entry"] > 0
                    and i <= ids.get(ret.get("repeat_of"), -1) <= j):  # it returns to a phrase of this drop
                breaks.append(j + 1)
                j += 2
                continue
            break
        beats_in = sum(phrases[k]["n_beats"] for k in range(i, j + 1) if k not in breaks)
        if beats_in < MIN_DROP_BEATS:
            i += 1
            continue
        runs.append({"first": i, "last": j, "breaks": breaks, "entry": ev["entry"],
                     "entry_stem": ev["entry_stem"], "hit": ev["hit"], "hit_kind": ev["hit_kind"],
                     "conf": round(conf, 4), "via_repeat": via_repeat, "threshold": round(thr, 4)})
        for k in range(i, j + 1):
            run_of[phrases[k]["id"]] = len(runs) - 1
        i = j + 1
    return runs


def _span_end_near(spans: list[dict], t: float, bl: float, tol: tuple[float, float]) -> list[dict]:
    return [s for s in spans if t - tol[0] * bl <= s["end"] <= t + tol[1] * bl]


def carve_before_drop(ctx: Ctx, s: float, floor: float) -> dict:
    """Pre-Drop (near-silence ending at the drop) then Fill (roll / riser /
    vocal pickup ending where the silence starts, or at the drop if none)."""
    bl = ctx.bl
    out: dict = {"pre_drop": None, "fill": None}
    gaps = [r for r in ctx.silences
            if s - GAP_END_TOL[0] * bl <= r["end"] <= s + GAP_END_TOL[1] * bl
            and (r["end"] - r["start"]) <= PREDROP_MAX_BEATS * bl and r["start"] >= floor]
    p0 = s
    if gaps:
        g = max(gaps, key=lambda r: r["end"] - r["start"])
        a, snapped = ctx.snap(max(g["start"], floor))
        out["pre_drop"] = {"start": a, "end": s, "snapped": snapped, "depth": g["depth"],
                           "silence": [g["start"], g["end"]]}
        p0 = a
    sig: list[tuple[str, float, float]] = []
    for kind, spans in (("snare_roll", ctx.rolls), ("riser", ctx.risers)):
        for sp in _span_end_near(spans, p0, bl, FILL_END_TOL):
            sig.append((kind, sp["start"], sp["confidence"]))
    for vp in ctx.vocal_phrases:
        if p0 - FILL_END_TOL[0] * bl <= vp["end"] <= p0 + FILL_END_TOL[1] * bl \
                and vp["start"] >= p0 - FILL_MAX_BEATS * bl:
            sig.append(("vocal_pickup", vp["start"], 0.5))
    if sig:
        f0 = max(min(x[1] for x in sig), p0 - FILL_MAX_BEATS * bl, floor)
        if p0 - f0 >= bl:
            a, snapped = ctx.snap(f0)
            if p0 - a >= bl * 0.5:
                out["fill"] = {"start": a, "end": p0, "snapped": snapped,
                               "kinds": sorted({x[0] for x in sig}),
                               "signal_conf": round(float(np.mean([x[2] for x in sig])), 4)}
    return out


def _evidence_start(ctx: Ctx, carve_start: float, cap_beats: float, floor: float,
                    sweeps: list[dict]) -> float | None:
    """Earliest roll / riser / opening-filter-sweep start whose span reaches into the
    window [carve_start - cap, carve_start], never before `floor`."""
    lo = max(floor, carve_start - cap_beats * ctx.bl)
    spans = [(sp["start"], sp["end"]) for sp in ctx.rolls + ctx.risers] + sweeps
    starts = [a for a, b in spans if b > lo and a < carve_start]
    return max(lo, min(starts)) if starts else None


def label_song(ctx: Ctx, phrases: list[dict], hint: dict | None) -> dict:
    """The proposal body (units + blocks), or status `kept_current` with no blocks."""
    prior = prior_from_hint(hint)
    n = len(phrases)
    runs = find_runs(ctx, phrases, prior)
    if prior["second_wave"] and len(runs) == 1:
        runs = find_runs(ctx, phrases, prior, threshold_delta=-0.15)
    if not runs:
        reason = "no phrase start has a kick/bass entry together with a hit"
        if prior["expect_no_drop"]:
            reason += " (the hint expects no drop for this song)"
        return {"status": "kept_current", "status_reason": reason, "prior": prior, "units": [], "blocks": []}

    # ---- phrase-level labels: (label, confidence, why, unit, extra) ---------
    lab: list[dict | None] = [None] * n
    overrides: list[dict] = []   # sub-phrase intervals that replace the phrase label
    units: list[dict] = []
    run_label: list[str] = []

    def put(i, label, conf, why, unit=None, **extra):
        lab[i] = {"label": label, "confidence": round(float(conf), 3), "why": why, "unit": unit, **extra}

    ids = {p["id"]: k for k, p in enumerate(phrases)}
    sweeps = sorted({(w["start_s"], w["end_s"]) for p in phrases for w in (p.get("filter_sweeps") or [])
                     if w.get("direction") == "opening"})
    prev_end = 0  # first phrase index of the stretch before the next run
    for ri, r in enumerate(runs):
        d, a = r["first"], prev_end
        first = phrases[d]
        unit_id = f"unit-{ri + 1:02d}"
        # run label: sung -> Chorus (unless the hint says the chorus is not the drop)
        sung = (first.get("vocals_presence") or 0.0) >= SUNG_VOCALS and prior["sung_is_chorus"]
        label = "Chorus" if sung else "Drop"
        inherited = None
        rep = first.get("repeat_of")
        if rep in ids and ids[rep] < d:
            earlier = lab[ids[rep]]
            if earlier and earlier["label"] in ("Drop", "Chorus") and earlier["label"] != label:
                inherited = rep
                label = earlier["label"]
        run_label.append(label)
        drop_s = first["start_s"]
        carve = carve_before_drop(ctx, drop_s, phrases[d - 1]["start_s"])
        # ---- build chain -------------------------------------------------
        chain = d
        k = d - 1
        while k >= a and (build_like(phrases[k]) or (k == d - 1 and (carve["pre_drop"] or carve["fill"]))):
            chain = k
            k -= 1
        carve_start = (carve["fill"] or carve["pre_drop"] or {"start": drop_s})["start"]
        build_start = phrases[chain]["start_s"] if chain < d else None
        build_edge = "phrase_edge"
        cap = prior["build_cap_beats"] * ctx.bl
        # the stretch's first phrase (Intro / Breakdown by position) is never wholly a
        # Build-Up; a build that reaches into it starts where its own evidence starts
        if build_start is not None and (carve_start - build_start > cap or chain == a):
            ev_t = _evidence_start(ctx, carve_start, prior["build_cap_beats"], phrases[chain]["start_s"], sweeps)
            if ev_t is not None:
                build_start, snapped = ctx.snap(ev_t)
                build_edge = "evidence" if snapped else "evidence_unsnapped"
                if abs(build_start - phrases[chain]["start_s"]) < 1e-6:
                    build_edge = "phrase_edge"
            elif chain == a:
                chain = a + 1
                build_start = phrases[chain]["start_s"] if chain < d else None
            else:  # longer than a build can be and nothing to say where it starts
                build_start, chain = None, d
        unit_kind = "build_drop" if (build_start is not None or carve["pre_drop"] or carve["fill"]) else "drop_only"
        unit = {"id": unit_id, "kind": unit_kind, "label": label, "drop_start_s": drop_s,
                "entry": r["entry"], "entry_stem": r["entry_stem"], "hit": r["hit"], "hit_kind": r["hit_kind"],
                "confidence": r["conf"], "threshold": r["threshold"], "via_repeat": r["via_repeat"],
                "build_start_s": build_start,
                "pre_drop": carve["pre_drop"], "fill": carve["fill"], "inherited_from": inherited}
        # ---- stretch before the build ------------------------------------
        stretch_end = chain  # phrases a .. chain-1 are positional
        pre_build_idx = None
        if build_start is not None and build_edge == "phrase_edge" and stretch_end - 1 >= a + 1 \
                and phrases[stretch_end - 1]["n_beats"] <= PREBUILD_MAX_BEATS \
                and not build_like(phrases[stretch_end - 1]):
            pre_build_idx = stretch_end - 1
        for q in range(a, stretch_end):
            p = phrases[q]
            anchor = r["conf"]
            base = 0.5 * (p.get("confidence") or 0.0) + 0.5 * anchor
            if q == pre_build_idx:
                put(q, "Pre-Build", POS_FACTOR["Pre-Build"] * base, "phrase before the Build-Up", unit_id)
            elif a == 0 and q == 0:
                put(q, "Intro", POS_FACTOR["Intro"] * base, "first phrase of the song", unit_id)
            elif groove_on(p) and (p.get("kick_presence") or 0) >= GROOVE_ON and (p.get("bass_presence") or 0) >= GROOVE_ON:
                put(q, "Main", POS_FACTOR["Main"] * base, "kick and bass on, no drop entry", unit_id)
            elif a == 0:
                put(q, "Intro", POS_FACTOR["Intro"] * base, "before the first build, no full groove", unit_id)
            else:
                put(q, "Breakdown", POS_FACTOR["Breakdown"] * base, "kick and bass out after a drop", unit_id)
        # ---- build chain labels ------------------------------------------
        ev_all = []
        for q in range(chain, d):
            ev = build_like(phrases[q])
            ev_all += ev
            conf_b = 0.5 * r["conf"] + 0.5 * min(1.0, 0.4 + 0.2 * len(set(ev)))
            put(q, "Build-Up", conf_b, "build evidence: " + (", ".join(ev) or "fill/gap before the drop"), unit_id)
        if build_start is not None and build_edge != "phrase_edge":
            overrides.append({"lo": phrases[chain]["start_s"], "hi": build_start,
                              "label": "Breakdown" if a else "Intro",
                              "confidence": 0.5 * r["conf"], "why": "before the build's first roll/riser", "unit": unit_id,
                              "start_kind": "phrase_edge"})
        unit["build_evidence"] = sorted(set(ev_all))
        # ---- carve-outs ---------------------------------------------------
        if carve["fill"]:
            f = carve["fill"]
            overrides.append({"lo": f["start"], "hi": f["end"], "label": "Fill",
                              "confidence": 0.5 * r["conf"] + 0.5 * f["signal_conf"],
                              "why": "fill before the drop: " + ", ".join(f["kinds"]), "unit": unit_id,
                              "start_kind": "evidence" if f["snapped"] else "evidence_unsnapped"})
        if carve["pre_drop"]:
            g = carve["pre_drop"]
            overrides.append({"lo": g["start"], "hi": g["end"], "label": "Pre-Drop",
                              "confidence": 0.5 * r["conf"] + 0.5 * min(1.0, 0.5 + 0.5 * g["depth"]),
                              "why": "near-silence across all stems before the hit", "unit": unit_id,
                              "start_kind": "evidence" if g["snapped"] else "evidence_unsnapped"})
        # ---- the run itself ------------------------------------------------
        for q in range(r["first"], r["last"] + 1):
            p = phrases[q]
            if q in r["breaks"]:
                put(q, "Drop Break", POS_FACTOR["Drop Break"] * r["conf"], "groove falls out, then returns", unit_id)
                continue
            why = f"{r['entry_stem']} entry {r['entry']:.2f} + {r['hit_kind'] or 'no hit'} {r['hit']:.2f}" if q == r["first"] else "groove stays on"
            if inherited and q == r["first"]:
                why += f"; label inherited from {inherited}"
            c = r["conf"] if q == r["first"] else r["conf"] * 0.9
            put(q, label, c, why, unit_id, inherited_from=inherited if q == r["first"] else None)
        last = phrases[r["last"]]
        if r["last"] > r["first"] and last["n_beats"] <= POSTCHORUS_MAX_BEATS \
                and (last.get("bass_presence") or 0) >= GROOVE_ON and (last.get("kick_presence") or 0) < GROOVE_ON \
                and r["last"] not in r["breaks"]:
            put(r["last"], "Post-Chorus", POS_FACTOR["Post-Chorus"] * r["conf"], "bass on, kick off at the run's tail", unit_id)
        units.append(unit)
        prev_end = r["last"] + 1
    # ---- trailing stretch ------------------------------------------------
    last_run = runs[-1]
    last_conf = last_run["conf"]
    outro_from, total = n, 0
    for q in range(n - 1, prev_end - 1, -1):
        if outro_from < n and total + phrases[q]["n_beats"] > OUTRO_CAP_BEATS:
            break
        total += phrases[q]["n_beats"]
        outro_from = q
    for q in range(prev_end, n):
        p = phrases[q]
        base = 0.5 * (p.get("confidence") or 0.0) + 0.5 * last_conf
        if q >= outro_from:
            put(q, "Outro", POS_FACTOR["Outro"] * base, "after the last drop", units[-1]["id"])
        elif (p.get("kick_presence") or 0) >= GROOVE_ON and (p.get("bass_presence") or 0) >= GROOVE_ON:
            put(q, "Main", POS_FACTOR["Main"] * base, "kick and bass on after the last drop, no drop entry", units[-1]["id"])
        else:
            put(q, "Breakdown", POS_FACTOR["Breakdown"] * base, "kick or bass out after the last drop", units[-1]["id"])
    if prev_end >= n:  # the last drop runs to the end of the song
        q = n - 1
        p = phrases[q]
        if lab[q]["label"] in ("Drop", "Chorus") and q > last_run["first"] and p["n_beats"] <= OUTRO_MAX_BEATS \
                and (p.get("bass_presence") or 0) < GROOVE_ON:
            put(q, "Outro", POS_FACTOR["Outro"] * (0.5 * (p.get("confidence") or 0.0) + 0.5 * last_conf),
                "last short phrase, bass out", units[-1]["id"])

    # ---- Fills that close a phrase ------------------------------------------
    taken = [(o["lo"], o["hi"]) for o in overrides]
    for q in range(n - 1):
        p = phrases[q]
        if p["n_beats"] < CLOSE_FILL_MIN_PHRASE_BEATS or lab[q]["label"] == "Drop Break":
            continue
        end = p["end_s"]
        sigs = [sp for sp in ctx.rolls + ctx.risers
                if abs(sp["end"] - end) <= CLOSE_FILL_TOL_BEATS * ctx.bl
                and sp["end"] - sp["start"] >= CLOSE_FILL_MIN_SPAN_BEATS * ctx.bl]
        if not sigs:
            continue
        lo = max(min(s["start"] for s in sigs), end - CLOSE_FILL_MAX_BEATS * ctx.bl, p["start_s"])
        a, snapped = ctx.snap(lo)
        if any(not (end <= t0 or a >= t1) for t0, t1 in taken) or end - a < ctx.bl * 0.5:
            continue
        overrides.append({"lo": a, "hi": end, "label": "Fill",
                          "confidence": 0.5 * lab[q]["confidence"] + 0.5 * float(np.mean([s["confidence"] for s in sigs])),
                          "why": f"roll/riser closes the phrase ({lab[q]['label']})", "unit": lab[q]["unit"],
                          "start_kind": "evidence" if snapped else "evidence_unsnapped"})
        taken.append((a, end))

    blocks = _tile(phrases, lab, overrides, ctx.duration)
    return {"status": "named", "status_reason": None, "prior": prior, "units": units, "blocks": blocks}


def _tile(phrases, lab, overrides, duration) -> list[dict]:
    """Elementary intervals of (phrase edges + override edges); override wins; adjacent
    equal labels merge."""
    cuts = sorted({0.0, duration, *[p["start_s"] for p in phrases], *[p["end_s"] for p in phrases],
                   *[o["lo"] for o in overrides], *[o["hi"] for o in overrides]})
    edge_times = {p["start_s"] for p in phrases}
    starts = [p["start_s"] for p in phrases]
    atoms: list[dict] = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 1e-6:
            continue
        mid = (a + b) / 2
        i = max(0, bisect.bisect_right(starts, mid) - 1)
        ov = next((o for o in overrides if o["lo"] <= mid < o["hi"]), None)
        src = ov or lab[i]
        if a == 0.0:
            kind = "song_start"
        elif a in edge_times:
            kind = "phrase_edge"
        else:  # a boundary an override created (its start) or released (its end)
            kind = next((o["start_kind"] for o in overrides if o["lo"] == a), "evidence")
        atoms.append({"start_s": round(a, 3), "end_s": round(b, 3), "label": src["label"],
                      "confidence": src["confidence"], "why": [src["why"]], "unit": src.get("unit"),
                      "phrase_ids": [phrases[i]["id"]], "start_kind": kind,
                      "inherited_from": src.get("inherited_from")})
    merged: list[dict] = []
    for at in atoms:
        m = merged[-1] if merged else None
        if m and m["label"] == at["label"] and m["unit"] == at["unit"] and at["start_kind"] == "phrase_edge" \
                and m["label"] not in ("Fill", "Pre-Drop"):
            m["end_s"] = at["end_s"]
            m["confidence"] = round(min(m["confidence"], at["confidence"]), 3)
            for w in at["why"]:
                if w not in m["why"]:
                    m["why"].append(w)
            m["phrase_ids"] += [x for x in at["phrase_ids"] if x not in m["phrase_ids"]]
        else:
            merged.append(at)
    for k, m in enumerate(merged):
        m["id"] = f"name-{k + 1:02d}"
    return merged
