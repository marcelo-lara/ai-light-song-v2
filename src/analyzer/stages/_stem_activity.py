from __future__ import annotations

from pathlib import Path

import numpy as np


def estimate_stem_activity_by_beat(audio_path: str | Path, beat_times: list[float], song_end: float) -> list[float]:
    import soundfile as sf

    path = Path(audio_path)
    if not path.exists() or not beat_times:
        return [0.0 for _ in beat_times]

    audio, sample_rate = sf.read(str(path))
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = np.asarray(audio, dtype=float)
    if audio.size == 0:
        return [0.0 for _ in beat_times]

    envelope: list[float] = []
    for index, beat_time in enumerate(beat_times):
        end_time = beat_times[index + 1] if index + 1 < len(beat_times) else song_end
        start_frame = max(0, min(len(audio), int(round(beat_time * sample_rate))))
        end_frame = max(start_frame + 1, min(len(audio), int(round(end_time * sample_rate))))
        window = audio[start_frame:end_frame]
        if window.size == 0:
            envelope.append(0.0)
            continue
        envelope.append(float(np.sqrt(np.mean(np.square(window)))))

    maximum = max(envelope, default=0.0)
    if maximum <= 1e-8:
        return [0.0 for _ in envelope]
    return [round(value / maximum, 6) for value in envelope]