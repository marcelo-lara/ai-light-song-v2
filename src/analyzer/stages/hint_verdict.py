"""Phase-4 stage — `hint-verdict` (v3.11 item 22).

Does the published analysis agree with the web-researched pre-analysis hint?
Writes the `verdicts` block of `reference/pre-analysis/verdict.json`, beside the
`version_check` block (item 21, preserved). One row per non-null hint field,
`{"verdict": confirmed|refuted|unresolved, "evidence": {...}}`; evidence is
section ids and counts, never times. `refuted` needs a presence/absence
contradiction; any other disagreement, or missing evidence, is `unresolved`.
A null hint value gets no row.

Gate — no rows (`verdicts.status == "skipped"`, with `reason`) when
`version_check.version_mismatch` is true (`version_mismatch`), the family is
not `edm` / `pop_edm` (`family`), or the hint is schema `1.0` (`hint_schema`,
its `shape` carries no evidence). No hint file -> nothing written. A hint with
no `version_check` block, or a missing published input, raises `AnalysisError`.

Rules (constants below):
- `drops` (int): a *drop run* = consecutive sections labelled `Drop` /
  `Extended Drop` (a `Drop Break` between them continues the run). `pop_edm`
  also counts a *drop-like Chorus* run: `Chorus` sections with bass and drums
  both `playing` for >= 80 % of the section and mix loudness >= the 75th
  percentile of the song's section means. Counts equal -> confirmed. Hint 0
  with a labelled drop run, or hint >= 1 with no drop run and no drop-like
  Chorus (and at least one `function_status: known` section) -> refuted. Else
  unresolved (counts differ, segmenter noise).
- `has_build_ups` (bool) vs the count of `Build-Up` sections: true needs >= 1,
  false needs 0; the opposite is refuted.
- `chorus_is_drop` (bool): share of `Drop` / `Extended Drop` sections whose
  overlap with `arrangement_state.json` `vocals_phrase` is >= 25 % of the
  section (sung). Share >= 0.5 is "sung", 0 is "instrumental", between is
  mixed (unresolved). true needs sung, false needs instrumental. No Drop
  section -> unresolved.
- `vocals` (enum) vs `vocals_phrase` coverage of the song: `none` confirmed
  < 2 %, refuted >= 10 %; `full` confirmed >= 30 %, refuted < 5 %; `chops`
  confirmed 2-30 %, refuted at 0 or >= 50 %; otherwise unresolved.
- `bpm` (`genre.bpm`): the `version_check` delta (half/double folded) within
  3 % -> confirmed, else refuted (cannot occur past the gate; kept so the row
  is honest if the gate ever changes).

Nothing in the analysis reads `verdict.json`; it is never published at top
level and never reaches the MCP server. This stage changes no other file.
Deterministic: pure arithmetic over published files, no timestamps.
"""
from __future__ import annotations

from analyzer.exceptions import AnalysisError
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths
from analyzer.stages.version_check import BPM_TOLERANCE_PCT

DROP_FUNCTIONS = ("Drop", "Extended Drop")
RUN_CONTINUERS = ("Drop Break",)
VERDICT_FAMILIES = ("edm", "pop_edm")
SUNG_OVERLAP_MIN = 0.25
SUNG_SHARE_MIN = 0.5
CHORUS_FULL_BAND_MIN = 0.8
CHORUS_LOUDNESS_PERCENTILE = 0.75
VOCALS_NONE_MAX, VOCALS_NONE_REFUTE = 0.02, 0.10
VOCALS_FULL_MIN, VOCALS_FULL_REFUTE = 0.30, 0.05
VOCALS_CHOPS_MAX, VOCALS_CHOPS_REFUTE_MAX = 0.30, 0.50


def _row(verdict: str, **evidence: object) -> dict:
    return {"verdict": verdict, "evidence": evidence}


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _mix_means(sections: list[dict], loudness: dict) -> list[float]:
    order = loudness.get("source_order")
    frames = loudness.get("frames")
    if not isinstance(order, list) or "mix" not in order or not isinstance(frames, list):
        raise AnalysisError("loudness.json must carry source_order with 'mix' and frames.")
    idx = order.index("mix")
    out = []
    for s in sections:
        vals = [f["values"][idx] for f in frames if s["start"] <= f["time"] < s["end"]]
        out.append(sum(vals) / len(vals) if vals else 0.0)
    return out


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def _full_band_share(section: dict, blocks: list[dict]) -> float:
    dur = section["end"] - section["start"]
    if dur <= 0:
        return 0.0
    covered = sum(
        _overlap(section["start"], section["end"], b["start_s"], b["end_s"])
        for b in blocks
        if "bass" in b.get("playing", []) and "drums" in b.get("playing", [])
    )
    return covered / dur


def _runs(flags: list[bool], continuers: list[bool]) -> list[list[int]]:
    """Maximal index runs of True flags; a continuer flag bridges within a run
    but never starts or ends one."""
    runs: list[list[int]] = []
    cur: list[int] = []
    for i, (f, c) in enumerate(zip(flags, continuers)):
        if f:
            cur.append(i)
        elif c and cur:
            cur.append(i)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    trimmed = []
    for r in runs:
        while r and not flags[r[-1]]:
            r = r[:-1]
        if r:
            trimmed.append(r)
    return trimmed


def _vocal_coverage(arrangement: dict, duration: float) -> tuple[float, int] | None:
    phrases = arrangement.get("vocals_phrase")
    if not isinstance(phrases, list) or duration <= 0:
        return None
    spans = sorted((p["start_s"], p["end_s"]) for p in phrases)
    total, cur_end = 0.0, None
    for a, b in spans:
        if cur_end is None or a > cur_end:
            total += b - a
            cur_end = b
        elif b > cur_end:
            total += b - cur_end
            cur_end = b
    return total / duration, len(spans)


def _verdict_drops(value, family, sections, ids, flags_known, drop_runs, chorus_runs):
    labelled = len(drop_runs)
    like = len(chorus_runs) if family == "pop_edm" else 0
    observed = labelled + like
    ev = dict(
        expected=value,
        drop_runs=labelled,
        drop_section_ids=[ids[i] for r in drop_runs for i in r],
        drop_like_chorus_runs=like,
        drop_like_chorus_section_ids=[ids[i] for r in chorus_runs for i in r] if like else [],
    )
    if observed == value:
        return _row("confirmed", **ev)
    if flags_known and ((value == 0 and labelled > 0) or (value >= 1 and observed == 0)):
        return _row("refuted", **ev)
    return _row("unresolved", **ev)


def compute_verdicts(hint: dict, version_check: dict, sections_doc: dict, arrangement: dict, loudness: dict, info: dict, song_name: str) -> dict:
    block: dict = {
        "generated_from": {
            "hint": "reference/pre-analysis/structure.json",
            "sections": "sections.json",
            "arrangement_state": "arrangement_state.json",
            "loudness": "loudness.json",
            "info": "info.json",
        },
    }
    genre, shape = hint.get("genre"), hint.get("shape")
    if not isinstance(genre, dict) or not isinstance(shape, dict):
        raise AnalysisError(f"{song_name}: structure.json must carry 'genre' and 'shape' objects.")
    family = genre.get("family")
    reason = None
    if version_check.get("version_mismatch") is True:
        reason = "version_mismatch"
    elif family not in VERDICT_FAMILIES:
        reason = "family"
    elif hint.get("schema_version") == "1.0":
        reason = "hint_schema"
    if reason:
        return {**block, "status": "skipped", "reason": reason, "fields": {}}

    sections = sections_doc.get("sections")
    if not isinstance(sections, list) or not sections:
        raise AnalysisError(f"{song_name}: sections.json carries no sections.")
    ids = [s["section_id"] for s in sections]
    funcs = [s.get("function") for s in sections]
    known = any(s.get("function_status") == "known" for s in sections)
    blocks = arrangement.get("blocks") or []

    drop_flags = [f in DROP_FUNCTIONS for f in funcs]
    drop_runs = _runs(drop_flags, [f in RUN_CONTINUERS for f in funcs])
    fields: dict = {}

    def val(name):
        entry = shape.get(name)
        return entry.get("value") if isinstance(entry, dict) else None

    drops = val("drops")
    if drops is not None:
        chorus_runs: list[list[int]] = []
        if family == "pop_edm":
            means = _mix_means(sections, loudness)
            floor = _percentile(means, CHORUS_LOUDNESS_PERCENTILE)
            like = [
                f == "Chorus" and means[i] >= floor and _full_band_share(sections[i], blocks) >= CHORUS_FULL_BAND_MIN
                for i, f in enumerate(funcs)
            ]
            chorus_runs = _runs(like, [False] * len(like))
        fields["drops"] = _verdict_drops(drops, family, sections, ids, known, drop_runs, chorus_runs)

    builds = val("has_build_ups")
    if builds is not None:
        n = [i for i, f in enumerate(funcs) if f == "Build-Up"]
        ev = dict(expected=builds, build_up_sections=len(n), build_up_section_ids=[ids[i] for i in n])
        if not known:
            fields["has_build_ups"] = _row("unresolved", **ev)
        else:
            fields["has_build_ups"] = _row("confirmed" if bool(n) == builds else "refuted", **ev)

    cid = val("chorus_is_drop")
    if cid is not None:
        idx = [i for i, f in enumerate(drop_flags) if f]
        phrases = arrangement.get("vocals_phrase")
        ev = dict(expected=cid, drop_sections=len(idx), drop_section_ids=[ids[i] for i in idx])
        if not idx or not isinstance(phrases, list):
            fields["chorus_is_drop"] = _row("unresolved", **ev, sung_sections=None)
        else:
            sung = [
                i for i in idx
                if sum(_overlap(sections[i]["start"], sections[i]["end"], p["start_s"], p["end_s"]) for p in phrases)
                >= SUNG_OVERLAP_MIN * (sections[i]["end"] - sections[i]["start"])
            ]
            share = len(sung) / len(idx)
            state = "sung" if share >= SUNG_SHARE_MIN else "instrumental" if not sung else "mixed"
            ev.update(sung_sections=len(sung), sung_section_ids=[ids[i] for i in sung], drop_vocal_state=state)
            ok = (state == "sung") if cid else (state == "instrumental")
            bad = (state == "instrumental") if cid else (state == "sung")
            fields["chorus_is_drop"] = _row("confirmed" if ok else "refuted" if bad else "unresolved", **ev)

    vocals = shape.get("vocals")
    if vocals is not None:
        cov = _vocal_coverage(arrangement, float(info.get("duration") or 0))
        if cov is None:
            fields["vocals"] = _row("unresolved", expected=vocals, vocals_phrase_count=None, coverage_pct=None)
        else:
            frac, count = cov
            if vocals == "none":
                v = "confirmed" if frac < VOCALS_NONE_MAX else "refuted" if frac >= VOCALS_NONE_REFUTE else "unresolved"
            elif vocals == "full":
                v = "confirmed" if frac >= VOCALS_FULL_MIN else "refuted" if frac < VOCALS_FULL_REFUTE else "unresolved"
            elif vocals == "chops":
                v = "confirmed" if VOCALS_NONE_MAX <= frac <= VOCALS_CHOPS_MAX else (
                    "refuted" if frac == 0 or frac >= VOCALS_CHOPS_REFUTE_MAX else "unresolved")
            else:
                raise AnalysisError(f"{song_name}: shape.vocals {vocals!r} is not none/chops/full.")
            fields["vocals"] = _row(v, expected=vocals, vocals_phrase_count=count, coverage_pct=round(frac * 100, 1))

    if genre.get("bpm") is not None:
        delta = version_check.get("bpm_delta_pct")
        ev = dict(expected=genre["bpm"], analysed_bpm=info.get("bpm"), bpm_delta_pct=delta)
        if delta is None:
            fields["bpm"] = _row("unresolved", **ev)
        else:
            fields["bpm"] = _row("confirmed" if delta <= BPM_TOLERANCE_PCT else "refuted", **ev)

    return {**block, "status": "evaluated", "reason": None, "fields": fields}


def publish_hint_verdict(paths: SongPaths) -> str | None:
    """Writes `reference/pre-analysis/verdict.json`'s `verdicts` block. Returns
    the written path, or `None` when the song has no hint."""
    hint_path = paths.reference("pre-analysis", "structure.json")
    if not hint_path.exists():
        return None
    hint = read_json(hint_path)
    if not isinstance(hint, dict):
        raise AnalysisError(f"{hint_path.name} must contain a JSON object payload.")
    verdict_path = paths.reference("pre-analysis", "verdict.json")
    payload = read_json(verdict_path) if verdict_path.exists() else {}
    if not isinstance(payload, dict) or not isinstance(payload.get("version_check"), dict):
        raise AnalysisError("'hint-verdict' requires verdict.json's version_check block; run 'version-check' first.")
    docs = {}
    for label, path in (
        ("sections.json", paths.sections_output_path),
        ("arrangement_state.json", paths.arrangement_state_output_path),
        ("loudness.json", paths.loudness_output_path),
        ("info.json", paths.info_output_path),
    ):
        if not path.exists():
            raise AnalysisError(f"'hint-verdict' requires the published {label}; run the full pipeline first.")
        docs[label] = read_json(path)
        if not isinstance(docs[label], dict):
            raise AnalysisError(f"{label} must contain a JSON object payload.")
    payload["schema_version"] = SCHEMA_VERSION
    payload["song_name"] = paths.song_name
    payload["verdicts"] = compute_verdicts(
        hint, payload["version_check"], docs["sections.json"], docs["arrangement_state.json"],
        docs["loudness.json"], docs["info.json"], paths.song_name,
    )
    write_json(verdict_path, payload)
    return str(verdict_path)
