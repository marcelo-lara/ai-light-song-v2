"""Subprocess entry point for Omnizart drum transcription.

Runs in its own process (spawned by `drums.py::_transcribe_drums`) so a
transcription crash cannot take the pipeline process down with it.

**The pad_size==0 empty-slice bug.** The vendored
`omnizart/drum/prediction.py::predict()` ends with `return pred[:-pad_size]`.
`create_batches()` returns `pad_size = batch_size - len(last_batch)`, which is
`0` whenever the stem's mini-beat count divides evenly into full 32-wide
batches — and `pred[:-0]` is `pred[:0]`, an **empty array**, not "no
truncation" as the author intended. This silently produced zero drum events
for any song that happened to hit that divisibility, with no error raised at
any layer.

Confirmed by direct repro against this omnizart build:
  * `Charli-VonDutch`: 2688 hops / batch_size 32 -> pad_size 0 -> empty `pred`
  * `ayuni`:            2656 hops / batch_size 32 -> pad_size 0 -> empty `pred`
  * `Armin - Revolution`: 3276 hops -> pad_size 20 -> unaffected (this is why
    most of the corpus never showed the bug)

`_fixed_predict` below reimplements `predict()` with the off-by-zero fixed,
and is installed as `omnizart.drum.app.predict` (the name that module bound
via `from omnizart.drum.prediction import predict`) before `app.transcribe`
runs. The vendored package file itself is never edited — this only patches
the bound reference in this subprocess's memory.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _fixed_predict(patch_cqt_feature, model, mini_beat_per_seg, batch_size: int = 32):
    from omnizart.drum.prediction import create_batches, merge_batches
    import numpy as np

    batches, pad_size = create_batches(patch_cqt_feature, mini_beat_per_seg, b_size=batch_size)
    batch_pred = [model.predict(batch) for batch in batches]
    pred = merge_batches(np.array(batch_pred))
    # The fix: `pred[:-0]` is `pred[:0]` (empty), not "keep everything".
    return pred if pad_size == 0 else pred[:-pad_size]


def main(argv: list[str]) -> None:
    stem_path, model_path, midi_path = argv[1:4]

    # `omnizart/drum/__init__.py` runs `app = DrumTranscription()`, which
    # REASSIGNS the `app` attribute on the `omnizart.drum` package object to
    # that instance -- shadowing the `omnizart.drum.app` submodule via
    # attribute lookup (though the submodule stays registered in
    # `sys.modules` under its qualified name). So `import omnizart.drum.app
    # as drum_app_module` -- attribute-style resolution -- silently binds
    # `drum_app_module` to the DrumTranscription *instance*, not the module;
    # patching `.predict` on it then patches an unused instance attribute,
    # never the module global `transcribe()` actually reads. Go through
    # `sys.modules` directly to reach the real module.
    import omnizart.drum  # ensures 'omnizart.drum.app' is registered below
    drum_app_module = sys.modules["omnizart.drum.app"]
    from omnizart.drum import app

    drum_app_module.predict = _fixed_predict

    midi = app.transcribe(stem_path, model_path=model_path, output=midi_path)
    output_path = Path(midi_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(midi, "write"):
        midi.write(str(output_path))


if __name__ == "__main__":
    main(sys.argv)
