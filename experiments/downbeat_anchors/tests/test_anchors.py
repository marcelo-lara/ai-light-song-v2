from experiments.downbeat_anchors import anchors as A

T = [i * 0.5 for i in range(200)]
ALL = [True] * 200


def edge(t, kinds=("stem_enter:bass",), score=2.0, conflicts=(), snapped=True):
    return {"start_edge": {"t": t, "kinds": list(kinds), "score": score, "conflicts": list(conflicts),
                           "snapped": snapped}, "confidence": 0.8}


def anc(*idx):
    return [{"beat_index": i, "t": T[i], "score": 2.0, "confidence": 0.8} for i in idx]


def test_anchor_filter_requires_entry_or_impact_no_conflict_snapped_score():
    ph = [{}, edge(10.0), edge(20.0, kinds=("stem_exit:bass",)), edge(30.0, conflicts=("x",)),
          edge(40.0, snapped=False), edge(50.0, score=1.0), edge(60.0, kinds=("impact",))]
    assert [a["t"] for a in A.anchor_edges(ph)] == [10.0, 60.0]


def test_locate_drops_anchors_far_from_any_beat_and_dedupes():
    out = A.locate(T, [{"t": 5.01, "score": 1.6}, {"t": 5.02, "score": 2.0}, {"t": 5.25, "score": 3.0}])
    assert [a["beat_index"] for a in out] == [10]
    assert out[0]["score"] == 2.0


def test_count_in_fours_between_consistent_anchors():
    r = A.count(T, ALL, anc(10, 26), set(), reach=0)
    assert [d["beat_index"] for d in r["downbeats"]] == [10, 14, 18, 22, 26]
    assert r["spans"][0]["resolved"] is True


def test_phase_disagreement_marks_span_unresolved_and_emits_nothing_inside():
    r = A.count(T, ALL, anc(10, 25, 41), {12, 30}, reach=0)
    assert [s["resolved"] for s in r["spans"]] == [False, True]
    assert r["spans"][0]["reason"] == "phase_disagree"
    idx = [d["beat_index"] for d in r["downbeats"]]
    assert 12 not in idx and 30 not in idx          # allin1 never overrides an anchored span
    assert idx == [10, 25, 29, 33, 37, 41]  # second span (25->41) is 16 beats: resolved


def test_untrusted_beat_inside_span_is_unresolved():
    trusted = ALL[:]
    trusted[14] = False
    r = A.count(T, trusted, anc(10, 18), set(), reach=0)
    assert r["spans"][0]["reason"] == "off_grid" and len(r["downbeats"]) == 2


def test_allin1_only_where_no_anchor_reaches():
    r = A.count(T, ALL, anc(40, 48), {2, 42, 100}, reach=8)
    src = {d["beat_index"]: d["source"] for d in r["downbeats"]}
    assert src[2] == "allin1" and src[100] == "allin1" and 42 not in src
    assert src[32] == "counted_edge" and src[56] == "counted_edge" and 31 not in src


def test_reach_stops_at_untrusted_beat():
    trusted = ALL[:]
    trusted[54] = False
    r = A.count(T, trusted, anc(48), {56, 52}, reach=16)
    src = {d["beat_index"]: d["source"] for d in r["downbeats"]}
    assert src[52] == "counted_edge" and src[56] == "allin1"


def test_no_anchors_is_exactly_allin1():
    r = A.count(T, ALL, [], {3, 7})
    assert [(d["beat_index"], d["source"]) for d in r["downbeats"]] == [(3, "allin1"), (7, "allin1")]
