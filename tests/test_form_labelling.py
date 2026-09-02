from __future__ import annotations

import inspect
import unittest

import numpy as np

from analyzer.stages.sections.form import (
    FORM_FAMILY_ROLES,
    assign_form_roles,
    boundary_confidence,
    compute_repetition_groups,
    infer_form_family,
)


def _section(bar_start, bar_end, *, energy, onset, vocals, drums, harmonic, bass, chord=0):
    hist = np.zeros(12)
    hist[chord % 12] = 1.0
    vec = np.concatenate([np.array([energy, onset, 0.2, vocals, drums, harmonic, bass]), hist])
    norm = np.linalg.norm(vec)
    return {
        "bar_start": bar_start, "bar_end": bar_end,
        "start_s": float(bar_start * 2), "end_s": float(bar_end * 2),
        "bar_count": bar_end - bar_start,
        "energy": energy, "onset": onset, "flux": 0.2,
        "vocals": vocals, "drums": drums, "harmonic": harmonic, "bass": bass,
        "vector": (vec / norm) if norm else vec,
    }


def _steady_timing(n_beats=120, interval=0.5):
    return {"beats": [{"time": i * interval} for i in range(n_beats)]}


class FormFamilyTests(unittest.TestCase):
    def test_genre_is_not_a_parameter(self) -> None:
        params = set(inspect.signature(infer_form_family).parameters)
        self.assertNotIn("genre", params)
        self.assertNotIn("genre_result", params)

    def test_dance_form_from_kick_tempo_and_bass_dropout(self) -> None:
        sections = [
            _section(0, 8, energy=0.4, onset=0.4, vocals=0.0, drums=0.5, harmonic=0.3, bass=0.6),
            _section(8, 16, energy=0.2, onset=0.2, vocals=0.0, drums=0.45, harmonic=0.2, bass=0.1),   # dropout
            _section(16, 24, energy=0.9, onset=0.7, vocals=0.0, drums=0.6, harmonic=0.4, bass=0.9),   # re-entry
            _section(24, 32, energy=0.7, onset=0.5, vocals=0.0, drums=0.5, harmonic=0.3, bass=0.7),
        ]
        result = infer_form_family(sections, _steady_timing(), None)
        self.assertEqual(result["value"], "dance_form")
        self.assertTrue(result["evidence"]["has_bass_dropout"])
        self.assertEqual(result["provenance"], "inferred")

    def test_unknown_when_evidence_conflicts(self) -> None:
        sections = [
            _section(0, 8, energy=0.5, onset=0.3, vocals=0.1, drums=0.2, harmonic=0.5, bass=0.4),
            _section(8, 16, energy=0.5, onset=0.3, vocals=0.1, drums=0.2, harmonic=0.5, bass=0.45),
        ]
        wobbly = {"beats": [{"time": t} for t in np.cumsum(np.random.RandomState(0).uniform(0.3, 0.8, 80))]}
        result = infer_form_family(sections, wobbly, None)
        self.assertIn(result["value"], {"unknown", "song_form"})

    def test_human_form_family_breaks_tie_only_when_weak(self) -> None:
        sections = [
            _section(0, 8, energy=0.5, onset=0.3, vocals=0.1, drums=0.2, harmonic=0.5, bass=0.4),
            _section(8, 16, energy=0.5, onset=0.3, vocals=0.1, drums=0.2, harmonic=0.5, bass=0.42),
        ]
        facts = {"form_family": {"value": "dance_form"}}
        result = infer_form_family(sections, _steady_timing(), facts)
        # inferred evidence here is weak -> human value adopted
        self.assertEqual(result["value"], "dance_form")
        self.assertEqual(result["provenance"], "human-confirmed")


class RepetitionGroupTests(unittest.TestCase):
    def test_choruses_group_together_distinct_from_verses(self) -> None:
        verse = dict(energy=0.4, onset=0.3, vocals=0.5, drums=0.3, harmonic=0.4, bass=0.3, chord=0)
        chorus = dict(energy=0.8, onset=0.6, vocals=0.6, drums=0.6, harmonic=0.5, bass=0.6, chord=5)
        sections = [
            _section(0, 8, **verse),
            _section(8, 16, **chorus),
            _section(16, 24, **verse),
            _section(24, 32, **chorus),
        ]
        groups = compute_repetition_groups(sections)
        letters = [g["repetition_group"] for g in groups]
        self.assertEqual(letters[0], letters[2])   # verses
        self.assertEqual(letters[1], letters[3])   # choruses
        self.assertNotEqual(letters[0], letters[1])

    def test_varied_repeat_records_variant_of(self) -> None:
        base = dict(energy=0.4, onset=0.3, vocals=0.5, drums=0.3, harmonic=0.4, bass=0.3, chord=0)
        sections = [
            _section(0, 8, **base),
            _section(8, 16, **{**base, "energy": 0.62, "drums": 0.55, "onset": 0.5}),  # same section, varied
        ]
        groups = compute_repetition_groups(sections)
        self.assertEqual(groups[0]["repetition_group"], groups[1]["repetition_group"])
        self.assertEqual(groups[1]["variant_of"], 0)
        self.assertLess(groups[1]["similarity"], 1.0)


class FormRoleTests(unittest.TestCase):
    def test_roles_stay_inside_family_vocabulary(self) -> None:
        sections = [
            _section(0, 4, energy=0.1, onset=0.1, vocals=0.0, drums=0.1, harmonic=0.2, bass=0.1),
            _section(4, 12, energy=0.5, onset=0.6, vocals=0.0, drums=0.4, harmonic=0.3, bass=0.3),
            _section(12, 20, energy=0.95, onset=0.7, vocals=0.0, drums=0.7, harmonic=0.4, bass=0.9),
            _section(20, 24, energy=0.2, onset=0.2, vocals=0.0, drums=0.1, harmonic=0.2, bass=0.1),
        ]
        reps = [0.0, 0.2, 0.3, 0.1]
        roles = assign_form_roles(sections, reps, "dance_form")
        for row in roles:
            self.assertIn(row["form_role"], FORM_FAMILY_ROLES["dance_form"])
        self.assertEqual(roles[0]["form_role"], "intro")
        self.assertEqual(roles[-1]["form_role"], "outro")

    def test_pop_track_alternates_verse_chorus(self) -> None:
        v = dict(energy=0.4, onset=0.3, vocals=0.5, drums=0.3, harmonic=0.4, bass=0.3)
        c = dict(energy=0.85, onset=0.6, vocals=0.6, drums=0.6, harmonic=0.5, bass=0.6)
        sections = [
            _section(0, 4, energy=0.1, onset=0.1, vocals=0.0, drums=0.1, harmonic=0.2, bass=0.1),
            _section(4, 12, **v), _section(12, 20, **c),
            _section(20, 28, **v), _section(28, 36, **c),
        ]
        reps = [0.0, 0.7, 0.8, 0.7, 0.8]
        roles = [r["form_role"] for r in assign_form_roles(sections, reps, "song_form")]
        self.assertEqual(roles[1], "verse")
        self.assertEqual(roles[2], "chorus")


class BoundaryConfidenceTests(unittest.TestCase):
    def _beats(self, n, *, loud, onset, flux, chord):
        rows = []
        for i in range(n):
            hist = np.zeros(12)
            hist[chord % 12] = 1.0
            rows.append({
                "time": i * 0.5,
                "vector": np.concatenate([np.array([loud, onset, flux]), hist]),
            })
        return rows

    def test_sharp_agreeing_boundary_scores_higher_than_smooth_one(self) -> None:
        # Strong contrast: loud/onset/flux and chord all change at the boundary.
        left = self._beats(6, loud=0.2, onset=0.1, flux=0.1, chord=0)
        right = self._beats(6, loud=0.9, onset=0.8, flux=0.7, chord=7)
        for i, row in enumerate(right):
            row["time"] = 3.0 + i * 0.5
        beat_rows = left + right
        bar_starts = [0.0, 2.0, 3.0, 4.0]
        sharp = boundary_confidence(beat_rows, bar_starts, 3.0, onset_anchored=True,
                                    form_role_margin=0.35, beat_interval_s=0.5)

        flat = left + self._beats(6, loud=0.22, onset=0.12, flux=0.12, chord=0)
        for i, row in enumerate(flat[6:]):
            row["time"] = 3.0 + i * 0.5
        smooth = boundary_confidence(flat, bar_starts, 3.0, onset_anchored=False,
                                     form_role_margin=0.0, beat_interval_s=0.5)

        self.assertGreater(sharp["value"], smooth["value"])
        self.assertGreater(sharp["value"], 0.6)
        self.assertLess(smooth["value"], 0.4)
        self.assertIn("channel_strengths", sharp["terms"])

    def test_confidence_can_span_full_range(self) -> None:
        left = self._beats(6, loud=0.2, onset=0.1, flux=0.1, chord=0)
        ident = self._beats(6, loud=0.2, onset=0.1, flux=0.1, chord=0)
        for i, row in enumerate(ident):
            row["time"] = 3.0 + i * 0.5
        result = boundary_confidence(left + ident, [0.0, 3.0], 3.05,
                                     onset_anchored=False, form_role_margin=0.0, beat_interval_s=0.5)
        self.assertLess(result["value"], 0.25)


if __name__ == "__main__":
    unittest.main()
