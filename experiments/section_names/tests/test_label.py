import numpy as np

from experiments.section_names import label

BL = 0.5


def phrase(i, a, b, kick=0.0, bass=0.0, vocals=0.0, roll=0.0, repeat_of=None, conf=1.0, **kw):
    return {"id": f"phrase-{i:02d}", "start_s": a, "end_s": b, "n_beats": int(round((b - a) / BL)),
            "kick_presence": kick, "bass_presence": bass, "vocals_presence": vocals,
            "riser_density": 0.0, "snare_roll_density": roll, "filter_sweeps": [], "noise_sweep": False,
            "kick_dropout_near_end": None, "ends_on_gap": False, "repeat_of": repeat_of,
            "confidence": conf, **kw}


def cache(duration, on_ranges, impacts=(), silences=(), rolls=(), vocal_phrases=()):
    """kick+bass present (0.9) inside `on_ranges`, absent (0.0) elsewhere; one beat per 0.5 s."""
    n = int(duration / BL)
    beats = [i * BL for i in range(n)]
    on = [0.9 if any(a <= t < b for a, b in on_ranges) else 0.0 for t in beats]
    return {"beats": beats, "trusted": [True] * n, "beat_len": BL, "duration": duration,
            "series": {"kick_low": on, "bass": on, "vocals": [0.0] * n, "mix": [0.5] * n,
                       "drums": [0.5] * n, "harmonic": [0.5] * n},
            "silences": [{"start": a, "end": b, "depth": 1.0} for a, b in silences],
            "impacts": [{"start": t, "conf": c} for t, c in impacts],
            "vocal_phrases": [{"start": a, "end": b} for a, b in vocal_phrases],
            "primitives": {"snare_roll": [{"start": a, "end": b, "confidence": 0.9} for a, b in rolls],
                           "riser": [], "reverse_cymbal": []}}


def run(c, phrases, hint=None):
    return label.label_song(label.Ctx(c), phrases, hint)


def names(res):
    return [b["label"] for b in res["blocks"]]


def simple(impact_conf=1.0, drop_at=45.0):
    c = cache(120.0, [(drop_at, 120.0)], impacts=[(drop_at, impact_conf)])
    ph = [phrase(1, 0.0, 30.0), phrase(2, 30.0, drop_at, roll=0.4),
          phrase(3, drop_at, 120.0, kick=0.9, bass=0.9)]
    return c, ph


def test_build_drop_unit_names_intro_build_drop_and_tiles_the_song():
    res = run(*simple())
    assert res["status"] == "named"
    assert names(res) == ["Intro", "Build-Up", "Drop"]
    bl = res["blocks"]
    assert bl[0]["start_s"] == 0.0 and bl[-1]["end_s"] == 120.0
    assert all(a["end_s"] == b["start_s"] for a, b in zip(bl, bl[1:]))
    assert all(b["confidence"] is not None and 0.0 <= b["confidence"] <= 1.0 for b in bl)


def test_no_hit_means_no_drop_and_the_song_keeps_its_labels():
    c = cache(120.0, [(45.0, 120.0)])  # kick/bass enter, nothing hits
    _, ph = simple()
    res = run(c, ph)
    assert res["status"] == "kept_current" and res["blocks"] == [] and res["units"] == []


def test_gap_then_fill_then_pre_drop_are_two_sections_before_the_hit():
    c = cache(120.0, [(45.0, 120.0)], impacts=[(45.0, 1.0)], silences=[(43.5, 44.9)], rolls=[(40.0, 43.5)])
    ph = [phrase(1, 0.0, 30.0), phrase(2, 30.0, 45.0, roll=0.4), phrase(3, 45.0, 120.0, kick=0.9, bass=0.9)]
    res = run(c, ph)
    assert names(res) == ["Intro", "Build-Up", "Fill", "Pre-Drop", "Drop"]
    fill, pre = res["blocks"][2], res["blocks"][3]
    assert fill["end_s"] == pre["start_s"] == 43.5 and pre["end_s"] == 45.0
    assert pre["start_kind"] == "evidence"


def test_a_roll_without_a_gap_is_a_fill_only():
    c = cache(120.0, [(45.0, 120.0)], impacts=[(45.0, 1.0)], rolls=[(41.0, 44.8)])
    ph = [phrase(1, 0.0, 30.0), phrase(2, 30.0, 45.0, roll=0.4), phrase(3, 45.0, 120.0, kick=0.9, bass=0.9)]
    assert names(run(c, ph)) == ["Intro", "Build-Up", "Fill", "Drop"]


def test_a_drop_with_no_build_is_found_from_the_hit_and_the_entry():
    c = cache(120.0, [(45.0, 120.0)], impacts=[(45.0, 1.0)])
    ph = [phrase(1, 0.0, 45.0), phrase(2, 45.0, 120.0, kick=0.9, bass=0.9)]
    res = run(c, ph)
    assert names(res) == ["Intro", "Drop"] and res["units"][0]["kind"] == "drop_only"


def test_repeat_of_an_earlier_drop_inherits_its_label():
    c = cache(120.0, [(20.0, 40.0), (60.0, 80.0)], impacts=[(20.0, 1.0), (60.0, 1.0)])
    ph = [phrase(1, 0.0, 20.0), phrase(2, 20.0, 40.0, kick=0.9, bass=0.9, vocals=0.9),
          phrase(3, 40.0, 60.0), phrase(4, 60.0, 80.0, kick=0.9, bass=0.9, vocals=0.0, repeat_of="phrase-02"),
          phrase(5, 80.0, 120.0)]
    res = run(c, ph)
    assert names(res)[:5] == ["Intro", "Chorus", "Breakdown", "Chorus", "Outro"]
    assert res["units"][1]["inherited_from"] == "phrase-02"


def test_short_groove_gap_that_returns_to_the_drop_is_a_drop_break_a_long_one_is_a_breakdown():
    ph = [phrase(1, 0.0, 20.0), phrase(2, 20.0, 40.0, kick=0.9, bass=0.9),
          phrase(3, 40.0, 48.0), phrase(4, 48.0, 80.0, kick=0.9, bass=0.9, repeat_of="phrase-02"),
          phrase(5, 80.0, 120.0)]
    c = cache(120.0, [(20.0, 40.0), (48.0, 80.0)], impacts=[(20.0, 1.0), (48.0, 1.0)])
    assert names(run(c, ph))[:4] == ["Intro", "Drop", "Drop Break", "Drop"]
    ph[2] = phrase(3, 40.0, 80.0 - 8.0)  # no longer a short gap
    ph[3] = phrase(4, 72.0, 80.0, kick=0.9, bass=0.9, repeat_of="phrase-02")
    c = cache(120.0, [(20.0, 40.0), (72.0, 80.0)], impacts=[(20.0, 1.0), (72.0, 1.0)])
    assert "Drop Break" not in names(run(c, ph))


def test_outro_is_capped_and_earlier_trailing_phrases_are_not_outro():
    c = cache(300.0, [(45.0, 100.0)], impacts=[(45.0, 1.0)])
    ph = [phrase(1, 0.0, 45.0), phrase(2, 45.0, 100.0, kick=0.9, bass=0.9),
          phrase(3, 100.0, 180.0), phrase(4, 180.0, 300.0)]
    res = run(c, ph)
    assert names(res) == ["Intro", "Drop", "Breakdown", "Outro"]


def test_hint_is_a_prior_only_house_raises_the_bar_and_no_hint_is_the_default_run():
    c, ph = simple(impact_conf=0.1)  # entry 1.0, weak hit -> score .55
    assert run(c, ph)["status"] == "named"
    house = {"genre": {"subgenre": "house"}, "track": {}, "shape": {}}
    res = run(c, ph, house)
    assert res["status"] == "kept_current" and "expects no drop" in res["status_reason"]
    assert run(c, ph, None)["blocks"] == run(c, ph)["blocks"]
    trance = {"genre": {"subgenre": "trance"}, "track": {}, "shape": {}}
    assert run(c, ph, trance)["status"] == "named"


def test_radio_edit_makes_an_early_drop_normal():
    c = cache(120.0, [(10.0, 120.0)], impacts=[(10.0, 0.1)])
    ph = [phrase(1, 0.0, 10.0), phrase(2, 10.0, 120.0, kick=0.9, bass=0.9)]
    assert run(c, ph)["status"] == "kept_current"  # score .55 < .45 + .15 early penalty
    radio = {"genre": {}, "track": {"version": "radio_edit"}, "shape": {}}
    assert run(c, ph, radio)["status"] == "named"


def test_prior_from_hint_defaults_without_a_hint():
    p = label.prior_from_hint(None)
    assert p["used"] is False and p["delta"] == 0.0 and p["build_cap_beats"] == label.BUILD_CAP_BEATS


def test_a_drop_needs_a_full_entry_window_of_song_before_it():
    c = cache(120.0, [(1.5, 120.0)], impacts=[(1.5, 1.0)])
    ph = [phrase(1, 0.0, 1.5), phrase(2, 1.5, 120.0, kick=0.9, bass=0.9)]
    assert run(c, ph)["status"] == "kept_current"
