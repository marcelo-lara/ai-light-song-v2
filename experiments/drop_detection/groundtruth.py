"""Parse the five-hint drop-sequence convention out of `human_hints.json`.

A drop sequence is a contiguous run, in time order, of hints titled
`drop approach` -> `drop build` -> `drop tension` -> `drop impact` ->
`drop release`. The run is grouped by adjacency; there is no hint field
linking them.

Only `impact.start` is treated as scoreable ground truth (see README).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .paths import hints_path

PHASE_ORDER = ("approach", "build", "tension", "impact", "release")


@dataclass
class DropSequence:
    song: str
    phases: dict[str, tuple[float, float]]
    warnings: list[str] = field(default_factory=list)

    @property
    def impact(self) -> float:
        return self.phases["impact"][0]

    @property
    def span(self) -> tuple[float, float]:
        return self.phases["approach"][0], self.phases["release"][1]


def _phase_hints(payload: dict) -> list[tuple[str, float, float]]:
    out = []
    for hint in payload.get("human_hints", []):
        title = str(hint.get("title", "")).strip().casefold()
        if not title.startswith("drop "):
            continue
        phase = title[5:].strip()
        if phase in PHASE_ORDER:
            out.append((phase, float(hint["start_time"]), float(hint["end_time"])))
    out.sort(key=lambda row: row[1])
    return out


def load_sequences(song: str, *, strict: bool = False) -> list[DropSequence]:
    path = hints_path(song)
    if not path.exists():
        return []
    rows = _phase_hints(json.loads(path.read_text()))

    sequences: list[DropSequence] = []
    run: list[tuple[str, float, float]] = []
    for row in rows:
        expected = PHASE_ORDER[len(run)] if len(run) < len(PHASE_ORDER) else None
        if row[0] != expected:
            # Out-of-order phase: abandon the partial run and restart from here.
            if run:
                _fail(song, f"partial/out-of-order run {[r[0] for r in run]} before {row[0]} @{row[1]:.2f}s", strict)
            run = [row] if row[0] == "approach" else []
            continue
        run.append(row)
        if row[0] == "release":
            sequences.append(_finish(song, run))
            run = []
    if run:
        _fail(song, f"trailing partial run {[r[0] for r in run]}", strict)
    return sequences


def _finish(song: str, run: list[tuple[str, float, float]]) -> DropSequence:
    phases = {phase: (start, end) for phase, start, end in run}
    warnings = []
    for a, b in zip(PHASE_ORDER, PHASE_ORDER[1:]):
        gap = phases[b][0] - phases[a][1]
        if abs(gap) > 0.05:
            warnings.append(f"{a}->{b} gap {gap:+.3f}s")
    return DropSequence(song=song, phases=phases, warnings=warnings)


def _fail(song: str, message: str, strict: bool) -> None:
    text = f"{song}: {message}"
    if strict:
        raise ValueError(text)
    print(f"  ! {text}")


def impacts(song: str) -> list[float]:
    return sorted(seq.impact for seq in load_sequences(song))


def labelled_songs(songs: list[str]) -> list[str]:
    return [song for song in songs if impacts(song)]
