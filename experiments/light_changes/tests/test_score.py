from experiments.light_changes import score


def _bars():
    return [{"bar": i + 1, "start_s": i * 2.0, "end_s": i * 2.0 + 2.0, "irregular": False} for i in range(30)]


def test_hit_is_within_one_beat_and_role_is_separate():
    # beat = 0.5 s; target bars 8, 9, 16, 19, 23 of Medicine
    pts = [{"bar": 8, "time_s": 14.0, "role": "fill"}, {"bar": 9, "time_s": 16.4, "role": "build"}]
    rows = score.score_song("Medicine-MilkInc", pts, _bars())
    assert rows[0]["hit"] and rows[0]["got_role"] == "fill"
    assert rows[1]["hit"] and rows[1]["got_role"] == "build"           # 16.4 vs 16.0 s: within 0.5 s
    assert rows[2]["got_bar"] in (8, 9) and not rows[2]["hit"]


def test_no_points_is_a_miss_not_an_error():
    rows = score.score_song("Medicine-MilkInc", [], _bars())
    assert all(not r["hit"] and r["got_bar"] is None for r in rows)
