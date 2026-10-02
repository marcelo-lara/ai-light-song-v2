import numpy as np

from experiments.phrases import build

BEAT = 0.5


def cache(n=200, kick=None, bass=None, cands=None, duration=None):
    kick = kick if kick is not None else [0.9] * n
    return {
        "beats": [round(i * BEAT + 0.5, 4) for i in range(n)], "trusted": [True] * n,
        "beat_len": BEAT, "duration": duration or (n * BEAT + 1.0),
        "series": {"kick_low": kick, "bass": bass or [0.5] * n, "vocals": [0.0] * n,
                   "mix": [0.5] * n, "drums": [0.5] * n, "harmonic": [0.5] * n},
        "bands": [[0.3] * 7 for _ in range(n)],
        "candidates": cands or [], "primitives": {"riser": [], "reverse_cymbal": [],
                                                  "snare_roll": [], "pre_drop_gap": []},
    }


def presence_edge(t):
    return {"t": t, "kind": "presence_enter:bass", "group": "presence", "stem": "bass",
            "dir": "enter", "weight": 1.5, "conf": 1.5}


def test_phrases_tile_the_song_and_carry_no_bar_fields():
    c = cache(cands=[presence_edge(30.0), presence_edge(60.0)])
    ph = build.build_phrases(c, [])
    assert ph[0]["start_s"] == 0.0 and ph[-1]["end_s"] == c["duration"]
    assert all(a["end_s"] == b["start_s"] for a, b in zip(ph, ph[1:]))
    assert len(ph) == 3
    assert not any("bar" in k for p in ph for k in p)


def test_kick_presence_comes_from_the_series_and_dropout_is_detected():
    kick = [0.9] * 100 + [0.0] * 4 + [0.9] * 96
    ph = build.build_phrases(cache(kick=kick, cands=[presence_edge(52.0)]), [])
    # the first phrase ends at 52 s (beat 102): its last four beats carry no kick
    assert ph[0]["kick_presence"] > 0.9
    assert ph[0]["kick_dropout_near_end"] in (True, False)
    kick2 = [0.9] * 96 + [0.0] * 4 + [0.9] * 100
    ph2 = build.build_phrases(cache(kick=kick2, cands=[presence_edge(50.5)]), [])
    assert ph2[0]["kick_dropout_near_end"] is True


def test_dropout_is_null_when_the_phrase_has_no_kick_to_lose():
    ph = build.build_phrases(cache(kick=[0.0] * 200, cands=[presence_edge(50.0)]), [])
    assert ph[0]["kick_dropout_near_end"] is None


def test_missing_filter_sweep_file_is_null_not_empty():
    assert build.build_phrases(cache(), None)[0]["filter_sweeps"] is None
    assert build.build_phrases(cache(), [])[0]["filter_sweeps"] == []


def test_filter_sweep_assigned_to_the_phrase_holding_most_of_it():
    sw = [{"stem": "harmonic", "direction": "opening", "start_s": 20.0, "end_s": 40.0}]
    ph = build.build_phrases(cache(cands=[presence_edge(30.0)]), sw)
    assert len(ph[0]["filter_sweeps"]) == 1 and len(ph[1]["filter_sweeps"]) == 1  # 50 % in each


def test_noise_sweep_needs_every_band_rising():
    n = 16
    rising = np.tile(np.linspace(0.1, 0.9, n)[:, None], (1, 7))
    assert build.noise_sweep(rising)[0] is True
    one_band = np.full((n, 7), 0.3)
    one_band[:, 6] = np.linspace(0.1, 0.9, n)
    assert build.noise_sweep(one_band)[0] is False
    assert build.noise_sweep(np.zeros((3, 7))) == (None, None)


def test_coverage_is_the_union_fraction():
    assert build._coverage([{"start": 0, "end": 5}, {"start": 3, "end": 8}], 0, 16) == 0.5


def test_unresolved_edge_makes_both_neighbours_unresolved():
    bad = presence_edge(30.0)
    c = cache(cands=[bad])
    c["trusted"] = [False] * len(c["trusted"])  # no trusted beat anywhere
    ph = build.build_phrases(c, [])
    assert [p["resolved"] for p in ph] == [False, False]


def test_confidence_is_null_with_no_edges():
    assert build.build_phrases(cache(), [])[0]["confidence"] is None
