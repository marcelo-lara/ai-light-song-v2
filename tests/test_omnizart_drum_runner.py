from __future__ import annotations

import sys
import unittest

import numpy as np

from analyzer.stages._omnizart_drum_runner import _fixed_predict


class _FakeModel:
    """Returns a deterministic, distinguishable prediction per batch call."""

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, batch):
        self.calls += 1
        # shape matches what omnizart's real model.predict returns for one
        # batch (confirmed against the vendored drum_keras model):
        # [b_size, out_classes, mini_beat_per_seg, 1].
        b_size, time_dim, freq_dim, mini_beat_per_seg = batch.shape
        out_classes = 13
        value = float(self.calls)
        return np.full((b_size, out_classes, mini_beat_per_seg, 1), value, dtype=np.float64)


class FixedPredictPadSizeZeroTests(unittest.TestCase):
    """Pins the v3.9 fix for omnizart's `pred[:-pad_size]` empty-slice bug.

    Root cause (confirmed against the vendored omnizart build): when the
    number of mini-beat hops divides evenly into full 32-wide batches,
    `create_batches()` returns `pad_size == 0`, and the original
    `predict()`'s `pred[:-pad_size]` evaluates as `pred[:-0]` == `pred[:0]`
    -- an empty array. `Charli-VonDutch` (2688 hops) and `ayuni` (2656 hops)
    hit this; `Armin - Revolution` (3276 hops, pad_size 20) did not, which is
    why it went unnoticed across most of the corpus.
    """

    def test_pad_size_zero_returns_full_length_prediction(self) -> None:
        # mini_beat_per_seg=4, b_size=2, n=11 -> hops=8 -> pad_size == 0.
        mini_beat_per_seg = 4
        n_frames = 11
        feature = np.zeros((n_frames, 5, 5))
        model = _FakeModel()

        pred = _fixed_predict(feature, model, mini_beat_per_seg, batch_size=2)

        self.assertEqual(pred.shape, (n_frames, 13))
        self.assertGreater(model.calls, 0)

    def test_pad_size_nonzero_still_truncates_padding(self) -> None:
        # mini_beat_per_seg=4, b_size=2, n=10 -> hops=7 -> pad_size == 1.
        mini_beat_per_seg = 4
        n_frames = 10
        feature = np.zeros((n_frames, 5, 5))
        model = _FakeModel()

        pred = _fixed_predict(feature, model, mini_beat_per_seg, batch_size=2)

        self.assertEqual(pred.shape, (n_frames, 13))


class DrumAppModuleShadowingTests(unittest.TestCase):
    """Pins that patching must go through `sys.modules`, not attribute access.

    `omnizart/drum/__init__.py` runs `app = DrumTranscription()`, which
    reassigns the `app` attribute on the `omnizart.drum` package to that
    instance -- shadowing the `omnizart.drum.app` submodule for attribute-
    style lookups. `import omnizart.drum.app as x` therefore binds `x` to the
    DrumTranscription instance, not the module whose globals `transcribe()`
    actually reads `predict` from.
    """

    def test_attribute_style_import_yields_the_instance_not_the_module(self) -> None:
        import omnizart.drum
        import omnizart.drum.app as attribute_style

        self.assertNotIsInstance(attribute_style, type(sys.modules["omnizart.drum.app"]))
        self.assertIs(attribute_style, omnizart.drum.app)

    def test_sys_modules_lookup_reaches_the_real_module(self) -> None:
        import omnizart.drum  # noqa: F401  (ensures 'omnizart.drum.app' is registered)

        real_module = sys.modules["omnizart.drum.app"]
        self.assertTrue(hasattr(real_module, "predict"))

        from omnizart.drum import app

        self.assertIs(app.transcribe.__globals__, real_module.__dict__)


if __name__ == "__main__":
    unittest.main()
