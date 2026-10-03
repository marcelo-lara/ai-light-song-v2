from experiments.downbeat_reanchor import anchors as A

T = [i * 0.5 for i in range(64)]


def _run(impacts=(), entries=(), kicks=(), trusted=None, allin1=None):
    return A.reanchor(T, trusted or [True] * len(T), allin1 or {},
                      [{"t": t, "confidence": 1.0} for t in impacts],
                      [{"t": t, "confidence": 1.0} for t in entries], list(kicks), 0.5)


def test_every_bar_is_four_beats_and_times_untouched():
    r = _run(impacts=[T[6], T[14], T[22], T[30]])
    assert r["beats"][6]["downbeat"] and r["beats"][6]["beat"] == 1
    assert A.irregular_bars(r["beats"], [True] * len(T))["outside"] == 0
    assert len(r["beats"]) == len(T)


def test_disagreeing_anchors_make_unresolved_span_but_keep_fours():
    # impacts on residues 2 and 3 in the same run: one phase wins, the other is a disagreement
    r = _run(impacts=[T[6], T[10], T[14], T[19]])
    assert A.irregular_bars(r["beats"], [True] * len(T))["outside"] == 0
    assert any(l["downbeat"] and l["confidence"] is not None for l in r["beats"])
    lone = _run(impacts=[T[6], T[19]])
    assert all(lone["beats"][i]["confidence"] is None for i in (6, 10, 14, 18))
    assert lone["spans"] and not lone["spans"][0]["resolved"]


def test_no_anchor_uses_allin1_phase_unresolved():
    r = _run(allin1={5: 1, 9: 1, 13: 1})
    assert r["runs"][0]["source"] == "allin1" and r["runs"][0]["phase"] == 1
    assert all(l["confidence"] is None for l in r["beats"])
    assert r["beats"][5]["downbeat"]


def test_phase_may_change_across_off_grid_span_only():
    trusted = [not (28 <= i <= 33) for i in range(len(T))]
    r = A.reanchor(T, trusted, {}, [{"t": T[6], "confidence": 1.0}, {"t": T[10], "confidence": 1.0},
                                    {"t": T[43], "confidence": 1.0}, {"t": T[47], "confidence": 1.0}], [], [], 0.5)
    assert [x["phase"] for x in r["runs"]] == [2, 3]
    assert A.irregular_bars(r["beats"], trusted)["outside"] == 0


def test_kick_phase_votes_need_a_margin():
    def ev(t):
        return {"time": t - A.ASSIGN_LEAD_S, "confidence": 0.8, "echo_of": None}
    on_floor = [ev(t) for t in T]  # four on the floor: no phase information
    assert not A.kick_votes(A.beat_kick_strength(T, on_floor, 0.5), [(0, 63)])
    beat1_only = [ev(T[i]) for i in range(2, 64, 4)]
    v = A.kick_votes(A.beat_kick_strength(T, beat1_only, 0.5), [(0, 63)])
    assert v and all(x["beat_index"] % 4 == 2 for x in v)


def test_pickup_is_its_own_partial_bar():
    r = _run(impacts=[T[3], T[7], T[11]])
    assert r["beats"][0]["bar"] == 1 and r["beats"][3]["bar"] == 2
    assert A.irregular_bars(r["beats"], [True] * len(T))["strict"] >= 1
    assert A.irregular_bars(r["beats"], [True] * len(T))["outside"] == 0
