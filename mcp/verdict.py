"""Second pass over the hint verdicts (v3.11 item 23): the brief, the validators
and the two bounded write paths behind `write_verdict_pass` and
`write_verdict_check`.

Writes exactly two things, both in a song's inner folder: the `second_pass`
block of the song's verdict file (this module) and `verdict_check` rows
appended to the proposals queue (`proposals.py`). It never edits the hint, the
first-pass `verdicts` / `version_check` blocks or any analysis file. Path
components are separate string literals (never one joined fragment) so
`test_exposure.py`'s literal-substring grep does not mistake a bounded write
path for a read leak - same convention as `proposals.py`. Contract:
docs/mcp-definition.md, "Second pass over the verdicts".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from proposals import find_verdict_checks
from structure_hint import _find_time_key

_INNER_DIRNAME = "reference"
_VERDICT_DIRNAME = "pre-analysis"
_VERDICT_FILENAME = "verdict.json"

FIELDS = ("drops", "has_build_ups", "chorus_is_drop", "vocals", "bpm")
AUDIO_KINDS = ("stems", "drum_density", "dropouts", "loudness")
WEB_KIND = "web_search"
OPEN_VERDICTS = ("refuted", "unresolved")
PASS_VERDICTS = ("confirmed", "refuted")
WRONG = ("hint", "analysis")
_ENTRY_KEYS = ("verdict", "wrong", "evidence")
_READ_KEYS = ("read", "showed")


class VerdictError(Exception):
    """Raised for a refused call. Nothing is written when raised."""


def verdict_path(song_dir: Path) -> Path:
    return song_dir / _INNER_DIRNAME / _VERDICT_DIRNAME / _VERDICT_FILENAME


def build_brief(song: str) -> str:
    """The instructions, verbatim - the single source for both the tool and
    the MCP prompt `verdict_pass`."""
    return f"""Second pass over the hint verdicts of the song {song!r}.

The analysis compared the web-researched hint with the audio and left some
claims `refuted` or `unresolved` (the `verdicts` list). Either side can be the
one that is wrong: a mislabelled section refutes a true hint. For EACH listed
verdict, and only those:

1. Read the audio evidence through get_detail (the section ids in the verdict's
   evidence say where to look): stem entries and exits (`stem_summary` / stems
   scope), `drum_density`, `dropouts`, and loudness (the loudest stretches).
   Do all four; none may be skipped.
2. Run one targeted web search for THAT claim on the audio's version (check
   the song's version through get_song_overview first), and quote what the
   source said. A source's answer settles a verdict only together with audio
   evidence that does not contradict it, never alone: the audio outranks the
   web.
3. Decide:
   - the evidence supports the claim -> verdict "confirmed";
   - it contradicts the claim -> verdict "refuted", with wrong "hint" (the
     hint is mistaken) or "analysis" (the published analysis is mistaken).
     The verdict judges the analysis' agreement with the hint: when the
     hint's claim holds in the audio but the analysis lacks the labelling,
     answer "refuted" with wrong "analysis", not "confirmed".
   Answer every verdict the evidence can answer. Call
   write_verdict_pass(song={song!r}, results={{<field>: {{"verdict": ...,
   "wrong": "hint"|"analysis"|null, "evidence": {{"stems": {{"read": ...,
   "showed": ...}}, "drum_density": {{...}}, "dropouts": {{...}},
   "loudness": {{...}}, "web_search": {{...}} or null}}}}}}). `read` is what you
   looked at (section ids, scopes, sources), `showed` is what it showed.
   "wrong" is null for "confirmed". NEVER write a time: no timestamps,
   seconds, bars or beats anywhere; refer to sections by id.
4. Only a verdict that stays factually unanswerable after ALL of that - all
   four audio kinds read AND the web search done - is queued with
   write_verdict_check(song={song!r}, field=..., claim=..., evidence={{"stems":
   {{"read", "showed"}}, "drum_density": ..., "dropouts": ..., "loudness": ...,
   "web_search": ...}}, cannot_settle=<why those cannot settle it>,
   question=<one line the operator can answer yes or no, about the claim>).
   It is refused unless the verdict is `unresolved`, and refused when the same
   claim was already queued, answered or rejected: never re-ask. Never queue on
   an assumption or a shallow read.
5. A verdict whose `operator` is set is already answered: do not touch it. If
   a call is refused, fix what it names and call it again.

Neither tool edits the hint or any analysis file. The operator's answer
(`operator.answer` "confirmed" = the claim holds, "rejected" = it does not)
arrives through the debugger and is shown in the verdicts below.
"""


def _read(song_dir: Path) -> dict[str, Any]:
    path = verdict_path(song_dir)
    if not path.is_file():
        raise VerdictError(
            "the song has no verdict file: the verdict stages run after the analysis and "
            "need a structure hint (write_structure_hint, then run the analysis)"
        )
    with path.open("r", encoding="utf-8") as handle:
        doc = json.load(handle)
    if not isinstance(doc, dict):
        raise VerdictError("the verdict file is not a JSON object")
    return doc


def _first_pass(doc: dict[str, Any]) -> dict[str, Any]:
    block = doc.get("verdicts")
    if not isinstance(block, dict):
        raise VerdictError("the verdict file has no verdicts block: run the hint-verdict stage first")
    return block


def _entry(doc: dict[str, Any], field: str) -> dict[str, Any]:
    fields = (doc.get("second_pass") or {}).get("fields") or {}
    got = fields.get(field)
    return got if isinstance(got, dict) else {
        "verdict": None, "wrong": None, "evidence": None, "first_pass_verdict": None, "operator": None,
    }


def load_brief(song_dir: Path, song: str) -> dict[str, Any]:
    doc = _read(song_dir)
    block = _first_pass(doc)
    checks = find_verdict_checks(song_dir, song)
    rows = []
    for field, row in (block.get("fields") or {}).items():
        if row.get("verdict") not in OPEN_VERDICTS:
            continue
        entry = _entry(doc, field)
        check = checks.get(field)
        rows.append({
            "field": field,
            "verdict": row["verdict"],
            "evidence": row.get("evidence"),
            "second_pass": None if entry.get("verdict") is None else {
                "verdict": entry["verdict"], "wrong": entry.get("wrong"), "evidence": entry.get("evidence"),
            },
            "check": None if check is None else {
                "id": check["id"], "status": check["status"], "rejection_reason": check.get("rejection_reason"),
            },
            "operator": entry.get("operator"),
        })
    return {
        "brief": build_brief(song),
        "status": block.get("status"),
        "reason": block.get("reason"),
        "verdicts": rows,
    }


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerdictError(f"{name} must be a non-empty string")
    return value.strip()


def _evidence_item(value: Any, name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise VerdictError(f"{name} is required: an object {{read, showed}}")
    for key in value:
        if key not in _READ_KEYS:
            raise VerdictError(f"{name}.{key} is not a schema field")
    return {key: _text(value.get(key), f"{name}.{key}") for key in _READ_KEYS}


def validate_evidence(evidence: Any, name: str, *, web_required: bool) -> dict[str, Any]:
    if not isinstance(evidence, dict) or not evidence:
        raise VerdictError(f"{name} is required: the four audio evidence kinds {list(AUDIO_KINDS)}")
    for key in evidence:
        if key not in AUDIO_KINDS + (WEB_KIND,):
            raise VerdictError(f"{name}.{key} is not a schema field")
    out: dict[str, Any] = {k: _evidence_item(evidence.get(k), f"{name}.{k}") for k in AUDIO_KINDS}
    web = evidence.get(WEB_KIND)
    if web is None:
        if web_required:
            raise VerdictError(f"{name}.{WEB_KIND} is required: run the targeted web search and say what it showed")
        out[WEB_KIND] = None
    else:
        out[WEB_KIND] = _evidence_item(web, f"{name}.{WEB_KIND}")
    return out


def _check_no_time(value: Any) -> None:
    bad = _find_time_key(value)
    if bad:
        raise VerdictError(f"{bad}: a time-bearing field is not allowed - refer to sections by id")


def _write(song_dir: Path, doc: dict[str, Any]) -> None:
    with verdict_path(song_dir).open("w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")


def _open_row(block: dict[str, Any], field: Any, name: str) -> dict[str, Any]:
    if field not in FIELDS:
        raise VerdictError(f"{name} must be one of {list(FIELDS)}, got {field!r}")
    row = (block.get("fields") or {}).get(field)
    if not isinstance(row, dict):
        raise VerdictError(f"{name} {field!r} has no verdict row (the hint field is null or the stage skipped it)")
    return row


def write_pass(song_dir: Path, results: Any) -> dict[str, Any]:
    """Validate every result, then store them under `second_pass.fields`.
    All-or-nothing: one bad result refuses the whole call."""
    if not isinstance(results, dict) or not results:
        raise VerdictError("results must be a non-empty object keyed by field")
    _check_no_time(results)
    doc = _read(song_dir)
    block = _first_pass(doc)
    staged: dict[str, dict[str, Any]] = {}
    for field, result in results.items():
        name = f"results.{field}"
        row = _open_row(block, field, "results key")
        if row["verdict"] not in OPEN_VERDICTS:
            raise VerdictError(f"{name}: the first-pass verdict is {row['verdict']!r}; only refuted or unresolved verdicts get a second pass")
        if _entry(doc, field).get("operator") is not None:
            raise VerdictError(f"{name}: the operator already answered this claim")
        if not isinstance(result, dict):
            raise VerdictError(f"{name} must be an object")
        for key in result:
            if key not in _ENTRY_KEYS:
                raise VerdictError(f"{name}.{key} is not a schema field")
        for key in _ENTRY_KEYS:
            if key not in result:
                raise VerdictError(f"{name}.{key} is missing")
        verdict, wrong = result["verdict"], result["wrong"]
        if verdict not in PASS_VERDICTS:
            raise VerdictError(f"{name}.verdict must be one of {list(PASS_VERDICTS)} (an unanswerable claim goes to write_verdict_check), got {verdict!r}")
        if verdict == "refuted" and wrong not in WRONG:
            raise VerdictError(f"{name}.wrong must be one of {list(WRONG)} when refuted")
        if verdict == "confirmed" and wrong is not None:
            raise VerdictError(f"{name}.wrong must be null when confirmed")
        staged[field] = {
            "verdict": verdict,
            "wrong": wrong,
            "evidence": validate_evidence(result["evidence"], f"{name}.evidence", web_required=False),
            "first_pass_verdict": row["verdict"],
        }
    fields = doc.setdefault("second_pass", {}).setdefault("fields", {})
    for field, value in staged.items():
        fields[field] = {**value, "operator": _entry(doc, field).get("operator")}
    _write(song_dir, doc)
    return {"written": sorted(staged), "second_pass": {f: fields[f] for f in sorted(staged)}}


def prepare_check(
    song_dir: Path, song: str, field: Any, claim: Any, evidence: Any, cannot_settle: Any, question: Any,
) -> dict[str, Any]:
    """Validate a `verdict_check` against the verdict file and the queue; returns the cleaned fields. Raises
    `VerdictError` (nothing written) on any refusal."""
    _check_no_time({"field": field, "evidence": evidence})
    doc = _read(song_dir)
    row = _open_row(_first_pass(doc), field, "field")
    clean_claim = _text(claim, "claim")
    clean_evidence = validate_evidence(evidence, "evidence", web_required=True)
    clean_cannot = _text(cannot_settle, "cannot_settle")
    clean_question = _text(question, "question")
    if row["verdict"] != "unresolved":
        raise VerdictError(
            f"field {field!r} is {row['verdict']!r}, not unresolved: only a verdict the evidence "
            f"could not answer is queued (answer it with write_verdict_pass)"
        )
    entry = _entry(doc, field)
    if entry.get("verdict") is not None:
        raise VerdictError(f"field {field!r} is already settled by the second pass ({entry['verdict']})")
    if entry.get("operator") is not None:
        raise VerdictError(f"field {field!r} was already answered by the operator")
    prior = find_verdict_checks(song_dir, song).get(field)
    if prior is not None:
        reason = {"rejected": "was rejected by the operator and is not re-queued",
                  "approved": "was already approved by the operator",
                  "pending": "is already queued"}.get(prior["status"], "is already queued")
        raise VerdictError(f"a verdict_check for field {field!r} {reason} (id {prior['id']})")
    return {
        "field": field, "claim": clean_claim, "evidence": clean_evidence,
        "cannot_settle": clean_cannot, "question": clean_question,
    }
