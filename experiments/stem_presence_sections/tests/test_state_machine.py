from __future__ import annotations

from experiments.stem_presence_sections import state_machine as sm


def test_classify_bar_bass_on_drums_full_is_full():
    c = sm.classify_bar(
        level_bass=0.4, level_drums=0.6, level_vocals=0.0,
        p95_bass=1.0, p95_drums=1.0, p95_vocals=1.0,
    )
    assert c.bass_state == "on"
    assert c.drums_state == "full"
    assert sm.coarse_label(c.bass_state, c.drums_state) == "full"


def test_classify_bar_drums_off_bass_on_is_bass_only():
    c = sm.classify_bar(
        level_bass=0.4, level_drums=0.0, level_vocals=0.0,
        p95_bass=1.0, p95_drums=1.0, p95_vocals=1.0,
    )
    assert sm.coarse_label(c.bass_state, c.drums_state) == "bass_only"


def test_classify_bar_everything_off_is_stripped():
    c = sm.classify_bar(
        level_bass=0.0, level_drums=0.0, level_vocals=0.0,
        p95_bass=1.0, p95_drums=1.0, p95_vocals=1.0,
    )
    assert sm.coarse_label(c.bass_state, c.drums_state) == "stripped"


def test_vocals_never_affect_coarse_label():
    """The task's hard requirement: vocals toggling must never, by itself,
    create or remove a boundary. `coarse_label` must not even accept a
    vocals argument, so this is really a signature-shape guard, but we also
    confirm two bars that differ only in vocals presence at the classifier
    level still land on the same coarse label."""
    quiet = sm.classify_bar(0.4, 0.4, level_vocals=0.0, p95_bass=1.0, p95_drums=1.0, p95_vocals=1.0)
    loud_vocals = sm.classify_bar(0.4, 0.4, level_vocals=0.9, p95_bass=1.0, p95_drums=1.0, p95_vocals=1.0)
    assert sm.coarse_label(quiet.bass_state, quiet.drums_state) == \
        sm.coarse_label(loud_vocals.bass_state, loud_vocals.drums_state)
    assert quiet.vocals_present is False
    assert loud_vocals.vocals_present is True


def test_hysteresis_absorbs_a_short_dip():
    """A 1-bar dip inside an otherwise 10-bar `full` run (the Rapture drums
    dip case) must not create a 3-way split; it must be swallowed back into
    the run it interrupted. Bass never leaves ("on" throughout), only the
    drums tier blips for one bar."""
    states = [("on", "full")] * 5 + [("on", "off")] * 1 + [("on", "full")] * 5
    smoothed = sm.apply_hysteresis(states, min_bars=4)
    assert smoothed == ["full"] * 11


def test_hysteresis_keeps_a_run_at_least_min_bars():
    states = [("on", "full")] * 6 + [("off", "off")] * 6 + [("on", "full")] * 6
    smoothed = sm.apply_hysteresis(states, min_bars=4)
    assert smoothed == ["full"] * 6 + ["stripped"] * 6 + ["full"] * 6


def test_hysteresis_merges_leading_short_run_forward():
    states = [("on", "off")] * 2 + [("on", "full")] * 8
    smoothed = sm.apply_hysteresis(states, min_bars=4)
    assert smoothed == ["full"] * 10


def test_hysteresis_pins_a_known_step_onset_to_its_bar():
    """Regression for the Rapture `Rapture - Nadia Ali` bug: a bassline
    entry is a hard cut in `bass_state` (off -> on, and it PERSISTS), but the
    very first bar of the new state is contaminated by a lingering
    drums-stem bleed that reads `sparse` instead of `off` for that one bar,
    making its composite label `full` instead of `bass_only` — a 1-bar
    literal-label run sandwiched between a long `stripped` run and a long
    `bass_only` run. The smoothed output must place the boundary AT that
    bar (index 10), not one bar later, because the contaminated bar's own
    `bass_state` ("on") agrees with what follows, not what came before."""
    states = (
        [("off", "off")] * 10          # stripped, bars 0-9
        + [("on", "sparse")] * 1        # contaminated edge bar (index 10)
        + [("on", "off")] * 8           # bass_only, bars 11-18
    )
    smoothed = sm.apply_hysteresis(states, min_bars=4)
    assert smoothed == ["stripped"] * 10 + ["bass_only"] * 9
    assert smoothed[10] == "bass_only"  # the contaminated bar joins what follows


def test_hysteresis_keeps_a_real_4_bar_break_inside_a_drop():
    """Regression: a genuine 4-bar break (bass AND drums both drop) must
    survive even when its own leading edge bar is contaminated by a decaying
    drum hit (reads `drums_only` instead of `stripped` for that one bar) —
    splitting the real break into a 1-bar run + a 3-bar run, each
    individually shorter than `min_bars`, must not cause both to be
    swallowed back into the surrounding `full` sections."""
    states = (
        [("on", "full")] * 6           # full, before the break
        + [("off", "full")] * 1         # contaminated edge bar of the break
        + [("off", "off")] * 3          # the rest of the break
        + [("on", "full")] * 6          # full, after the break
    )
    smoothed = sm.apply_hysteresis(states, min_bars=4)
    assert smoothed.count("full") == 12
    break_run = smoothed[6:10]
    assert len(set(break_run)) == 1  # the whole break is ONE uniform section
    assert break_run[0] != "full"  # and it is not swallowed into `full`


def test_group_into_sections_matches_hysteresis_runs():
    bar_rows = [
        {"bar": i + 1, "start": float(i), "end": float(i + 1)} for i in range(10)
    ]
    smoothed = ["full"] * 6 + ["stripped"] * 4
    sections = sm.group_into_sections(smoothed, bar_rows)
    assert [s.label for s in sections] == ["full", "stripped"]
    assert sections[0].bar_start == 1 and sections[0].bar_end == 6
    assert sections[1].bar_start == 7 and sections[1].bar_end == 10
    assert sections[0].start_s == 0.0 and sections[0].end_s == 6.0
