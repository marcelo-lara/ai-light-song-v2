from __future__ import annotations

import collections
from collections import abc
import os
import numpy as np


os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "1")


_ABC_NAMES = (
    "Callable",
    "Iterable",
    "Iterator",
    "Mapping",
    "MutableMapping",
    "MutableSequence",
    "MutableSet",
    "Sequence",
    "Set",
)


for _name in _ABC_NAMES:
    if not hasattr(collections, _name):
        setattr(collections, _name, getattr(abc, _name))


_NUMPY_ALIASES = {
    "bool": bool,
    "complex": complex,
    "float": float,
    "int": int,
    "object": object,
}


for _name, _value in _NUMPY_ALIASES.items():
    if _name not in np.__dict__:
        setattr(np, _name, _value)


def _patch_madmom_downbeat_processor() -> None:
    try:
        import itertools as it

        from madmom.features.downbeats import DBNDownBeatTrackingProcessor, _process_dbn
    except Exception:
        return

    original_process = DBNDownBeatTrackingProcessor.process

    if getattr(original_process, "__name__", "") == "_compat_process":
        return

    def _compat_process(self, activations, **kwargs):
        first = 0
        if self.threshold:
            idx = np.nonzero(activations >= self.threshold)[0]
            if idx.any():
                first = max(first, np.min(idx))
                last = min(len(activations), np.max(idx) + 1)
            else:
                last = first
            activations = activations[first:last]

        if not activations.any():
            return np.empty((0, 2))

        results = list(self.map(_process_dbn, zip(self.hmms, it.repeat(activations))))
        best = int(np.argmax([score for _, score in results]))
        path, _ = results[best]
        st = self.hmms[best].transition_model.state_space
        om = self.hmms[best].observation_model
        positions = st.state_positions[path]
        beat_numbers = positions.astype(int) + 1

        if self.correct:
            beats = np.empty(0, dtype=np.int)
            beat_range = om.pointers[path] >= 1
            idx = np.nonzero(np.diff(beat_range.astype(np.int)))[0] + 1
            if beat_range[0]:
                idx = np.r_[0, idx]
            if beat_range[-1]:
                idx = np.r_[idx, beat_range.size]
            if idx.any():
                for left, right in idx.reshape((-1, 2)):
                    peak = np.argmax(activations[left:right]) // 2 + left
                    beats = np.hstack((beats, peak))
        else:
            beats = np.nonzero(np.diff(beat_numbers))[0] + 1

        return np.vstack(((beats + first) / float(self.fps), beat_numbers[beats])).T

    DBNDownBeatTrackingProcessor.process = _compat_process


_patch_madmom_downbeat_processor()