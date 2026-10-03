"""v3.11 item 23 - `get_verdict_brief` / `write_verdict_pass` / `write_verdict_check`.

Throwaway tmp roots only; the committed fixtures stay untouched."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = MCP_DIR / "tests" / "fixtures" / "analysis"


def _load(name: str, filename: str):
    sys.path.insert(0, str(MCP_DIR))
    spec = importlib.util.spec_from_file_location(name, MCP_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load("mcp_local_server_verdict", "server.py")
SONG = "McpFull - Fixture"


def _item(text: str = "ok") -> dict:
    return {"read": f"read {text}", "showed": f"showed {text}"}


def _evidence(web: bool = True) -> dict:
    ev = {k: _item(k) for k in ("stems", "drum_density", "dropouts", "loudness")}
    ev["web_search"] = _item("web") if web else None
    return ev


def _verdict_doc() -> dict:
    row = lambda v: {"verdict": v, "evidence": {"expected": 2, "drop_section_ids": ["section-003"]}}
    return {
        "schema_version": "3.1", "song_name": SONG,
        "version_check": {"version_mismatch": False, "duration_delta_s": 1.0, "bpm_delta_pct": 0.1},
        "verdicts": {"status": "evaluated", "reason": None, "generated_from": {}, "fields": {
            "drops": row("unresolved"), "has_build_ups": row("refuted"),
            "vocals": row("confirmed"), "chorus_is_drop": row("unresolved"),
        }},
    }


@pytest.fixture()
def root(tmp_path, monkeypatch):
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    shutil.copytree(FIXTURE_ROOT / SONG, analysis / SONG)
    monkeypatch.setenv("MCP_ANALYSIS_ROOT", str(analysis))
    pre = analysis / SONG / "reference" / "pre-analysis"
    pre.mkdir(parents=True)
    (pre / "verdict.json").write_text(json.dumps(_verdict_doc(), indent=2))
    return analysis


def _vpath(root: Path) -> Path:
    return root / SONG / "reference" / "pre-analysis" / "verdict.json"


def _qpath(root: Path) -> Path:
    return root / SONG / "reference" / "proposals" / "pending.json"


def _queue(root: Path) -> list:
    return json.loads(_qpath(root).read_text())["proposals"] if _qpath(root).exists() else []


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _check_args(**over) -> dict:
    args = dict(song=SONG, field="drops", claim="The song has two drops.", evidence=_evidence(),
                cannot_settle="Stems and loudness disagree.", question="Does it have two drops?")
    args.update(over)
    return args


def test_brief_is_the_prompt_and_lists_open_verdicts(root) -> None:
    out = server.get_verdict_brief(SONG)
    prompt = asyncio.run(server.server.get_prompt("verdict_pass", {"song": SONG}))
    assert prompt.messages[0].content.text == out["brief"]
    low = out["brief"].lower()
    for needle in ("drum_density", "dropouts", "loudness", "stem", "web search", "never alone",
                   "never write a time", "never re-ask", "unresolved"):
        assert needle in low
    assert [r["field"] for r in out["verdicts"]] == ["drops", "has_build_ups", "chorus_is_drop"]
    assert out["verdicts"][0] == {
        "field": "drops", "verdict": "unresolved",
        "evidence": {"expected": 2, "drop_section_ids": ["section-003"]},
        "second_pass": None, "check": None, "operator": None,
    }


def test_brief_without_verdict_file_errors(tmp_path, monkeypatch) -> None:
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    shutil.copytree(FIXTURE_ROOT / SONG, analysis / SONG)
    monkeypatch.setenv("MCP_ANALYSIS_ROOT", str(analysis))
    for fn, args in ((server.get_verdict_brief, (SONG,)),
                     (server.write_verdict_pass, (SONG, {"drops": {}}))):
        with pytest.raises(ToolError, match="no verdict file"):
            fn(*args)
    with pytest.raises(ToolError, match="no verdict file"):
        server.write_verdict_check(**_check_args())
    assert not (analysis / SONG / "reference").exists()


def test_unknown_song_refused(root) -> None:
    with pytest.raises(ToolError):
        server.get_verdict_brief("No Such Song")


def test_pass_round_trips_and_touches_only_second_pass(root) -> None:
    before = json.loads(_vpath(root).read_text())
    other = {k: v for k, v in _tree(root).items() if not k.endswith("verdict.json")}
    out = server.write_verdict_pass(SONG, {
        "drops": {"verdict": "confirmed", "wrong": None, "evidence": _evidence(web=False)},
        "has_build_ups": {"verdict": "refuted", "wrong": "analysis", "evidence": _evidence()},
    })
    assert out["written"] == ["drops", "has_build_ups"]
    after = json.loads(_vpath(root).read_text())
    assert {k: v for k, v in after.items() if k != "second_pass"} == before
    f = after["second_pass"]["fields"]
    assert f["drops"] == {"verdict": "confirmed", "wrong": None, "evidence": _evidence(web=False),
                          "first_pass_verdict": "unresolved", "operator": None}
    assert f["has_build_ups"]["wrong"] == "analysis" and f["has_build_ups"]["first_pass_verdict"] == "refuted"
    assert {k: v for k, v in _tree(root).items() if not k.endswith("verdict.json")} == other
    row = server.get_verdict_brief(SONG)["verdicts"][0]
    assert row["second_pass"]["verdict"] == "confirmed"


def _good_result() -> dict:
    return {"verdict": "confirmed", "wrong": None, "evidence": _evidence()}


def _pass_mutations():
    def unknown_field(r): return ("bogus", r)
    def confirmed_first(r): return ("vocals", r)
    def nofield_extra(r): r["extra"] = 1; return ("drops", r)
    def time_key(r): r["evidence"]["stems"]["start_s"] = "x"; return ("drops", r)
    def time_top(r): r["timestamp"] = 3; return ("drops", r)
    def no_evidence(r): r["evidence"] = {}; return ("drops", r)
    def none_evidence(r): r["evidence"] = None; return ("drops", r)
    def missing_kind(r): del r["evidence"]["dropouts"]; return ("drops", r)
    def no_showed(r): r["evidence"]["loudness"]["showed"] = " "; return ("drops", r)
    def bad_evidence_key(r): r["evidence"]["guess"] = _item(); return ("drops", r)
    def bad_verdict(r): r["verdict"] = "unresolved"; return ("drops", r)
    def refuted_no_wrong(r): r["verdict"] = "refuted"; return ("drops", r)
    def refuted_bad_wrong(r): r["verdict"] = "refuted"; r["wrong"] = "both"; return ("drops", r)
    def confirmed_wrong(r): r["wrong"] = "hint"; return ("drops", r)
    def web_incomplete(r): r["evidence"]["web_search"] = {"read": "x"}; return ("drops", r)
    return [("results key", unknown_field), ("first-pass verdict", confirmed_first), ("results.drops.extra", nofield_extra),
            ("start_s", time_key), ("timestamp", time_top), ("evidence", no_evidence), ("evidence", none_evidence),
            ("dropouts", missing_kind), ("loudness.showed", no_showed), ("guess", bad_evidence_key),
            ("verdict", bad_verdict), ("wrong", refuted_no_wrong), ("wrong", refuted_bad_wrong),
            ("wrong", confirmed_wrong), ("web_search.showed", web_incomplete)]


@pytest.mark.parametrize("match,mutate", _pass_mutations())
def test_pass_refusals_write_nothing(root, match, mutate) -> None:
    before = _tree(root)
    field, result = mutate(_good_result())
    with pytest.raises(ToolError, match=match):
        server.write_verdict_pass(SONG, {field: result})
    assert _tree(root) == before


def test_pass_is_all_or_nothing_and_empty_refused(root) -> None:
    before = _tree(root)
    with pytest.raises(ToolError):
        server.write_verdict_pass(SONG, {"drops": _good_result(), "vocals": _good_result()})
    with pytest.raises(ToolError, match="non-empty"):
        server.write_verdict_pass(SONG, {})
    assert _tree(root) == before


def test_pass_leaves_hint_and_analysis_untouched(root) -> None:
    before = {k: v for k, v in _tree(root).items() if not k.endswith("verdict.json")}
    server.write_verdict_pass(SONG, {"drops": _good_result()})
    server.write_verdict_check(**_check_args(field="chorus_is_drop"))
    assert {k: v for k, v in _tree(root).items()
            if not (k.endswith("verdict.json") or k.endswith("pending.json"))} == {
        k: v for k, v in before.items()}


def test_check_appends_a_verdict_check_row(root) -> None:
    entry = server.write_verdict_check(**_check_args())
    assert entry["type"] == "verdict_check" and entry["status"] == "pending"
    assert entry["verdict_check"] == {
        "field": "drops", "claim": "The song has two drops.", "evidence": _evidence(),
        "cannot_settle": "Stems and loudness disagree.", "question": "Does it have two drops?",
    }
    assert _queue(root) == [entry]
    assert server.get_verdict_brief(SONG)["verdicts"][0]["check"] == {
        "id": entry["id"], "status": "pending", "rejection_reason": None}


def test_check_coexists_with_hint_proposals(root) -> None:
    server.propose_hint(SONG, start=1.0, end=2.0, title="t", summary="s", evidence="e")
    server.write_verdict_check(**_check_args())
    assert [e["type"] for e in _queue(root)] == ["hint", "verdict_check"]


def _check_mutations():
    def noclaim(a): a["claim"] = ""
    def noclaim_none(a): a["claim"] = None
    def noevidence(a): a["evidence"] = {}
    def noweb(a): a["evidence"]["web_search"] = None
    def noweb_key(a): del a["evidence"]["web_search"]
    def nostems(a): del a["evidence"]["stems"]
    def nodensity(a): a["evidence"]["drum_density"] = {"read": "x"}
    def nodropouts(a): a["evidence"]["dropouts"]["showed"] = ""
    def noloud(a): a["evidence"]["loudness"] = None
    def nowebshowed(a): a["evidence"]["web_search"]["showed"] = "  "
    def nocannot(a): a["cannot_settle"] = ""
    def noquestion(a): a["question"] = ""
    def badfield(a): a["field"] = "tempo"
    def timeev(a): a["evidence"]["stems"]["onset"] = "x"
    def confirmed(a): a["field"] = "vocals"
    def refuted(a): a["field"] = "has_build_ups"
    return [("claim", noclaim), ("claim", noclaim_none), ("evidence", noevidence), ("web_search", noweb),
            ("web_search", noweb_key), ("stems", nostems), ("drum_density.showed", nodensity),
            ("dropouts.showed", nodropouts), ("loudness", noloud), ("web_search.showed", nowebshowed),
            ("cannot_settle", nocannot), ("question", noquestion), ("field", badfield), ("onset", timeev),
            ("not unresolved", confirmed), ("not unresolved", refuted)]


@pytest.mark.parametrize("match,mutate", _check_mutations())
def test_check_refusals_write_nothing(root, match, mutate) -> None:
    args = copy.deepcopy(_check_args())
    mutate(args)
    before = _tree(root)
    with pytest.raises(ToolError, match=match):
        server.write_verdict_check(**args)
    assert _tree(root) == before
    assert not _qpath(root).exists()


def test_duplicate_pending_check_refused(root) -> None:
    server.write_verdict_check(**_check_args())
    with pytest.raises(ToolError, match="already queued"):
        server.write_verdict_check(**_check_args())
    assert len(_queue(root)) == 1


def test_rejected_check_is_not_requeued(root) -> None:
    server.write_verdict_check(**_check_args())
    queue = json.loads(_qpath(root).read_text())
    queue["proposals"][0].update(status="rejected", rejection_reason="Operator heard one drop.")
    _qpath(root).write_text(json.dumps(queue))
    before = _tree(root)
    with pytest.raises(ToolError, match="rejected by the operator and is not re-queued"):
        server.write_verdict_check(**_check_args(claim="Reworded: two drops overall."))
    assert _tree(root) == before
    assert server.get_verdict_brief(SONG)["verdicts"][0]["check"]["rejection_reason"] == "Operator heard one drop."
    # a different claim (another field) is still allowed
    server.write_verdict_check(**_check_args(field="chorus_is_drop"))


def test_approved_check_operator_answer_is_readable(root) -> None:
    entry = server.write_verdict_check(**_check_args())
    # what the debugger's approve flow writes (item 24): queue status + `operator` on the verdict
    queue = json.loads(_qpath(root).read_text())
    queue["proposals"][0]["status"] = "approved"
    _qpath(root).write_text(json.dumps(queue))
    doc = json.loads(_vpath(root).read_text())
    operator = {"answer": "confirmed", "reason": None, "check_id": entry["id"]}
    doc["second_pass"] = {"fields": {"drops": {
        "verdict": None, "wrong": None, "evidence": None, "first_pass_verdict": None, "operator": operator}}}
    _vpath(root).write_text(json.dumps(doc))
    row = server.get_verdict_brief(SONG)["verdicts"][0]
    assert row["operator"] == operator
    assert row["check"]["status"] == "approved"
    # answered: neither a pass nor a new check may overwrite it
    with pytest.raises(ToolError, match="operator already answered"):
        server.write_verdict_pass(SONG, {"drops": _good_result()})
    with pytest.raises(ToolError, match="already answered by the operator"):
        server.write_verdict_check(**_check_args())


def test_settled_field_cannot_be_queued(root) -> None:
    server.write_verdict_pass(SONG, {"drops": _good_result()})
    with pytest.raises(ToolError, match="already settled"):
        server.write_verdict_check(**_check_args())


def test_pass_preserves_a_prior_operator_entry_shape(root) -> None:
    server.write_verdict_pass(SONG, {"drops": _good_result()})
    f = json.loads(_vpath(root).read_text())["second_pass"]["fields"]["drops"]
    assert set(f) == {"verdict", "wrong", "evidence", "first_pass_verdict", "operator"}
