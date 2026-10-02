from experiments.phrases import detect

BEAT = 0.5
BEATS = [i * BEAT for i in range(0, 400)]  # 0 .. 199.5 s


def c(t, group, weight, kind=None, stem=None, direction="hit"):
    return {"t": t, "kind": kind or group, "group": group, "stem": stem,
            "dir": direction, "weight": weight, "conf": weight}


def edges(cands, trusted=None, duration=200.0):
    return detect.detect_edges(cands, BEATS, trusted or [True] * len(BEATS), BEAT, duration)


def test_lone_impact_is_not_an_edge():
    assert edges([c(50.0, "impact", 0.6)]) == []


def test_bass_entry_plus_impact_is_an_edge_at_the_nearest_beat():
    e = edges([c(50.1, "arr:bass", 1.0, "stem_enter:bass", "bass", "enter"), c(50.2, "impact", 0.6)])
    assert len(e) == 1 and e[0]["t"] == 50.0 and e[0]["snapped"] and e[0]["conflicts"] == []


def test_presence_boundary_alone_clears_the_threshold():
    assert len(edges([c(80.0, "presence", 1.5, "presence_enter:bass", "bass", "enter")])) == 1


def test_edge_in_off_grid_span_moves_to_a_trusted_beat_not_an_untrusted_one():
    trusted = [not (49.0 <= b <= 50.4) for b in BEATS]  # beat 50.0 untrusted
    e = edges([c(50.0, "presence", 1.5, "presence_enter:bass", "bass", "enter")], trusted)
    assert e[0]["t"] == 50.5 and e[0]["snapped"]


def test_no_trusted_beat_nearby_keeps_physical_time_and_flags_it():
    trusted = [not (45.0 <= b <= 55.0) for b in BEATS]
    e = edges([c(50.0, "presence", 1.5, "presence_enter:bass", "bass", "enter")], trusted)
    assert e[0]["t"] == 50.0 and not e[0]["snapped"]
    assert any(x.startswith("grid") for x in e[0]["conflicts"])


def test_stem_enter_and_exit_in_one_cluster_is_a_direction_conflict():
    e = edges([c(60.0, "arr:drums", 1.0, "stem_enter:drums", "drums", "enter"),
               c(60.5, "presence", 1.5, "presence_exit:drums", "drums", "exit")])
    assert any(x.startswith("direction") for x in e[0]["conflicts"])


def test_stem_sources_far_apart_are_a_position_conflict():
    e = edges([c(60.0, "presence", 1.5, "presence_enter:bass", "bass", "enter"),
               c(61.4, "arr:bass", 1.0, "stem_enter:bass", "bass", "enter")])
    assert any(x.startswith("position") for x in e[0]["conflicts"])


def test_presence_time_wins_over_a_later_arrangement_time():
    e = edges([c(60.0, "presence", 1.5, "presence_enter:bass", "bass", "enter"),
               c(61.0, "arr:bass", 1.0, "stem_enter:bass", "bass", "enter")])
    assert e[0]["onset_s"] == 60.0


def test_edges_closer_than_min_phrase_keep_the_stronger():
    e = edges([c(50.0, "presence", 1.5, "presence_enter:bass", "bass", "enter"),
               c(51.6, "presence", 2.4, "presence_exit:drums", "drums", "exit")])
    assert [x["t"] for x in e] == [51.5]


def test_edges_near_song_start_and_end_are_dropped():
    assert edges([c(1.0, "presence", 1.5), c(199.0, "presence", 1.5)]) == []
