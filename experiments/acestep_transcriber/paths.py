"""Where the ACE-Step Transcriber experiment reads and writes.

Independent of `src/analyzer` and of the sibling experiments' code. Shares the
output file `reference/proposals/vocal_transcription.json` with
`experiments/vocalparse` — its `sources` list is keyed by model name, so this
experiment rewrites only its own `ACE-Step …` entry (and the `whisper-…`
baseline row) and leaves the rest alone. That is a data dependency on a file,
not an import.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("ACESTEP_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]

PROPOSAL_NAME = "vocal_transcription.json"
SOURCE_MODEL = "ACE-Step Transcriber (ACE-Step/acestep-transcriber)"


def all_songs() -> list[str]:
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (SONGS_ROOT / f"{p.name}.mp3").exists()
    )


def audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def vocal_stem_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / "vocals.wav"


def moises_lyrics_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "moises" / "lyrics.json"


def shipped_sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def human_hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def allin1_proposal_path(song: str) -> Path:
    """The sibling experiment's form read, for the structure comparison."""
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "allin1.json"


def proposal_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / PROPOSAL_NAME


def raw_cache_path(song: str) -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT / f"{song.replace('/', '_')}.acestep.json"


#: The whisper-large-v3 baseline is identical for both singing-transcription
#: experiments (same model, same vocal stem), so its cache is shared — computed
#: once, read by whichever experiment runs. Still a file dependency, not a code
#: import.
WHISPER_CACHE_ROOT = Path(__file__).resolve().parents[1] / ".whisper_baseline_cache"


def whisper_cache_path(song: str) -> Path:
    WHISPER_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return WHISPER_CACHE_ROOT / f"{song.replace('/', '_')}.whisper.json"


def out_file(name: str) -> Path:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    return OUT_ROOT / name


def moises_words(song: str) -> list[dict]:
    path = moises_lyrics_path(song)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())
    return [
        {"start": float(r["start"]), "end": float(r["end"]), "text": str(r["text"])}
        for r in rows
        if str(r.get("text", "")) not in ("<SOL>", "<EOL>")
    ]


def human_impacts(song: str) -> list[float]:
    path = human_hints_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return sorted(
        float(h["start_time"]) for h in payload.get("human_hints", [])
        if str(h.get("title", "")).strip().casefold() == "drop impact"
    )
