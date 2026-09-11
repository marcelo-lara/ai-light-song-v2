"""The shared proposal shape every voiceness candidate (items 4-7) writes.

One shape lets four independently-built candidates be read against each other
on one timeline and scored through one scorer (`scorer.py`). A candidate
writes:

    * a per-50ms-frame `voiceness` series, each frame carrying its own
      `confidence` (never folded into the value — a low-confidence frame is
      itself signal, per CLAUDE.md "confidence is a separate numeric field"),
    * derived `vocal_phrase` blocks: `{start, end, confidence}` spans, the
      merged/segmented reading of the frame series into "a phrase happens
      here" for the timeline and for boundary-F1 scoring.

Dataclasses, matching `experiments/vocal_phrases/detector.py`'s own
`Envelope`/style rather than TypedDict.
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "1.0"


@dataclass
class VoicenessFrame:
    """One 50ms-grid sample. `voiceness` is a score in [0, 1] (a hard
    detector emits 0.0/1.0); `confidence` is `None` when the producer has no
    honest confidence to report — never guessed (no silent fallbacks)."""

    time_s: float
    voiceness: float
    confidence: float | None = None

    def as_tuple(self) -> tuple[float, float]:
        """The `(time_s, voiceness_bool_or_score)` shape `scorer.py` reads."""
        return (self.time_s, self.voiceness)


@dataclass
class VocalPhrase:
    start: float
    end: float
    confidence: float | None = None

    def to_dict(self) -> dict:
        return {
            "start": round(float(self.start), 3),
            "end": round(float(self.end), 3),
            "confidence": None if self.confidence is None else round(float(self.confidence), 3),
        }


@dataclass
class VoicenessProposal:
    """One candidate's full output for one song."""

    song_name: str
    experiment: str
    engine: str
    frames: list[VoicenessFrame] = field(default_factory=list)
    vocal_phrase: list[VocalPhrase] = field(default_factory=list)
    #: Extra `generated_from` fields specific to the candidate (params,
    #: source stem/model, checkpoint hash, ...). Merged in verbatim.
    generated_from_extra: dict = field(default_factory=dict)
    interval_ms: int = 50

    def to_proposal_json(self) -> dict:
        """The `reference/proposals/<experiment>.json` shape.

        Top-level metadata mirrors the convention already in
        `reference/proposals/texture_novelty.json` / `phrase_periodicity.json`
        (`schema_version`, `song_name`, `generated_from`); the dense
        `frames`/`metadata` pairing mirrors the published `loudness.json`
        convention for a per-frame series.
        """
        generated_from = {
            "experiment": self.experiment,
            "engine": self.engine,
            **self.generated_from_extra,
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "song_name": self.song_name,
            "generated_from": generated_from,
            "metadata": {
                "interval_ms": self.interval_ms,
                "total_frames": len(self.frames),
            },
            "frames": [
                {
                    "time": round(f.time_s, 3),
                    "voiceness": round(float(f.voiceness), 4),
                    "confidence": None if f.confidence is None else round(float(f.confidence), 3),
                }
                for f in self.frames
            ],
            "vocal_phrase": [p.to_dict() for p in self.vocal_phrase],
        }

    def write(self, path: Path) -> dict:
        payload = self.to_proposal_json()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return payload


def frames_as_tuples(frames: list[VoicenessFrame]) -> list[tuple[float, float]]:
    """Convenience: the `(time_s, voiceness)` pairs `scorer.py` consumes."""
    return [f.as_tuple() for f in frames]


def phrases_as_dicts(phrases: list[VocalPhrase]) -> list[dict]:
    return [p.to_dict() for p in phrases]
