from __future__ import annotations

import unittest

import numpy as np

from analyzer.stages.timing import _downbeat_scores, _local_phase_vote, _phase_assignment


class DownbeatScoresTests(unittest.TestCase):
    def test_samples_nearest_frame_at_100hz(self) -> None:
        activation = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], dtype=np.float64)
        # frame index = round(time * 100): 0.0 -> 0, 0.03 -> 3, 0.049 -> 5
        scores = _downbeat_scores([0.0, 0.03, 0.049], activation, fps=100.0)
        self.assertEqual(scores, [0.1, 0.4, 0.6])

    def test_clamps_to_last_frame_past_activation_end(self) -> None:
        activation = np.array([0.1, 0.9], dtype=np.float64)
        scores = _downbeat_scores([10.0], activation, fps=100.0)
        self.assertEqual(scores, [0.9])

    def test_empty_activation_yields_zero_scores(self) -> None:
        scores = _downbeat_scores([0.0, 1.0], np.array([], dtype=np.float64), fps=100.0)
        self.assertEqual(scores, [0.0, 0.0])


class LocalPhaseVoteTests(unittest.TestCase):
    def test_picks_position_that_wins_the_most_local_groups(self) -> None:
        # Position 2 is the local arg-max in every one of 3 groups.
        scores = [0.1, 0.1, 0.9, 0.1] * 3
        self.assertEqual(_local_phase_vote(scores), 2)

    def test_a_single_outsized_group_does_not_dominate_the_vote(self) -> None:
        # One group has a huge but out-of-phase spike; the other two groups
        # agree on position 1. A magnitude sum would be won by the spike
        # (10.0 alone beats 0.9 * 2); the majority vote is not.
        scores = [0.1, 0.9, 0.1, 0.1, 0.0, 0.9, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0]
        self.assertEqual(_local_phase_vote(scores), 1)

    def test_defaults_to_zero_when_shorter_than_one_group(self) -> None:
        self.assertEqual(_local_phase_vote([0.5, 0.2]), 0)

    def test_ties_keep_the_earliest_position(self) -> None:
        # Group 1 votes for position 0, group 2 votes for position 1 — a tie.
        scores = [0.9, 0.1, 0.1, 0.1, 0.1, 0.9, 0.1, 0.1]
        self.assertEqual(_local_phase_vote(scores), 0)


class PhaseAssignmentTests(unittest.TestCase):
    def test_assigns_beat_in_bar_and_confidence_from_scores(self) -> None:
        # Two clean 4/4 bars, downbeat at every 4th beat from index 0, inside
        # one window.
        scores = [0.9, 0.1, 0.1, 0.1, 0.8, 0.2, 0.1, 0.1]
        assignment = _phase_assignment(scores, window_bars=1)
        beat_in_bars = [a[0] for a in assignment]
        confidences = [a[1] for a in assignment]
        self.assertEqual(beat_in_bars, [1, 2, 3, 4, 1, 2, 3, 4])
        self.assertEqual(confidences[0], 0.9)
        self.assertEqual(confidences[4], 0.8)
        # Non-downbeat positions never carry a confidence value.
        self.assertTrue(all(confidences[i] is None for i in (1, 2, 3, 5, 6, 7)))

    def test_marks_unknown_when_local_argmax_disagrees_with_assigned_downbeat(self) -> None:
        # Two bars share one window. The first bar's own peak sits at
        # position 2, the second bar's peak sits at position 0 — a tie in the
        # window's vote, broken toward the earliest position (0). Bar one's
        # assigned downbeat (position 0) therefore disagrees with that bar's
        # own local arg-max (position 2): a whole-beat local disagreement, so
        # its confidence must be None even though it has a real, non-zero
        # score. Bar two's own local argmax agrees with the assigned phase.
        scores = [0.3, 0.1, 0.9, 0.1, 0.8, 0.1, 0.1, 0.1]
        assignment = _phase_assignment(scores, window_bars=2)
        self.assertIsNone(assignment[0][1])
        self.assertEqual(assignment[4][1], 0.8)

    def test_handles_incomplete_trailing_bar(self) -> None:
        scores = [0.9, 0.1, 0.1, 0.1, 0.7, 0.2]
        assignment = _phase_assignment(scores, window_bars=1)
        beat_in_bars = [a[0] for a in assignment]
        self.assertEqual(beat_in_bars, [1, 2, 3, 4, 1, 2])
        self.assertEqual(assignment[4][1], 0.7)

    def test_phase_can_drift_between_windows(self) -> None:
        # Window 1 (first 4 bars, 16 beats) has its downbeat at position 0;
        # window 2 (next 4 bars) has drifted to position 2. A single global
        # phase could not satisfy both; per-window voting should.
        window1 = ([0.9, 0.1, 0.1, 0.1] * 4)
        window2 = ([0.1, 0.1, 0.9, 0.1] * 4)
        assignment = _phase_assignment(window1 + window2, window_bars=4)
        beat_in_bars = [a[0] for a in assignment]
        self.assertEqual(beat_in_bars[:4], [1, 2, 3, 4])
        # Position 2 of the second window is the new downbeat (relative index
        # 2 within the window maps to beat_in_bar == 1).
        self.assertEqual(beat_in_bars[16:20], [3, 4, 1, 2])


if __name__ == "__main__":
    unittest.main()
