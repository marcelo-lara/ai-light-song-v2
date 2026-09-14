from __future__ import annotations

from experiments.truth_common import energy_tension as et


def _truth():
    return [
        et.RatedSegment("fixture", 0.0, 10.0, energy=2, tension=1, source="human", provisional=False),
        et.RatedSegment("fixture", 10.0, 20.0, energy=4, tension=5, source="human", provisional=False),
        et.RatedSegment("fixture", 20.0, 30.0, energy=3, tension=2, source="seed", provisional=True),
    ]


def test_exact_and_within_1_match():
    predicted = [
        {"start": 0.0, "end": 10.0, "energy": 2, "tension": 3},  # tension off by 2
        {"start": 10.0, "end": 20.0, "energy": 5, "tension": 5},  # energy off by 1
        {"start": 20.0, "end": 30.0, "energy": 3, "tension": 2},  # seed, exact
    ]
    scores = et.score_energy_tension("fixture", predicted, truth=_truth())
    by = {(s.field, s.source): s for s in scores}

    assert by[("energy", "human")].exact_match == 1  # only first row exact
    assert by[("energy", "human")].within_1 == 2  # both within 1

    assert by[("tension", "human")].exact_match == 1  # only second row exact
    assert by[("tension", "human")].within_1 == 1  # tension off by 2 fails within-1 too

    assert by[("energy", "seed")].provisional is True
    assert by[("energy", "seed")].exact_match == 1


def test_missing_seed_file_produces_no_seed_rows_not_a_crash():
    truth = [et.RatedSegment("fixture", 0.0, 10.0, energy=2, tension=1, source="human", provisional=False)]
    scores = et.score_energy_tension("fixture", [{"start": 0.0, "end": 10.0, "energy": 2, "tension": 1}], truth=truth)
    assert all(s.source != "seed" for s in scores)
