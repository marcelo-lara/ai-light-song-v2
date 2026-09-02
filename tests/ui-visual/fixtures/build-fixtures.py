#!/usr/bin/env python3
"""Rebuild the frozen visual-regression fixtures under fixtures/analysis/.

Source of truth:
  RegFull  <- data/analysis/Armin - Revolution  (real mp3, all artifacts, human_hints)
  RegPartial <- RegFull minus artifacts/essentia/fft_bands.json (degraded banner)
  _test_song <- data/analysis/_test_song (synthetic, no audio)

WARNING: `reference/human/human_hints.json` in the fixtures is HAND-CURATED, not
a faithful copy of the source song. `hint-drag.spec.ts` depends on three
clearly-separated blocks (hint-001 40-48, hint-002 52-60, hint-003 64-72) that do
not exist in the real track. Re-running this script overwrites them with the live
values and breaks that spec, so `git checkout` those three files (or re-curate
them) after any rebuild.

Dense per-frame arrays (fft_bands / rms_loudness / loudness_envelope) are
decimated to ~60 evenly spaced frames, keeping the first and last frame so the
song's full duration is still represented. info.json / beats.json are copied
verbatim so full-extent checks stay meaningful.
"""
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC_ANALYSIS = REPO / "data" / "analysis"
SRC_SONGS = Path("/home/darkangel/ai-dmx-light-render/data/songs")
OUT = Path(__file__).resolve().parent / "analysis"
OUT_SONGS = Path(__file__).resolve().parent / "songs"

REG_SOURCE = "Armin - Revolution"

# Files the UI actually loads (ui/src/data/paths.ts + App.tsx TIMELINE_KEYS).
NEEDED = [
    "info.json",
    "beats.json",
    "sections.json",
    "song_event_timeline.json",
    "reference/human/human_hints.json",
    "reference/proposals/drop_impacts.json",
    "artifacts/essentia/fft_bands.json",
    "artifacts/essentia/rms_loudness.json",
    "artifacts/essentia/loudness_envelope.json",
    "artifacts/layer_a_harmonic.json",
    "artifacts/layer_b_symbolic.json",
    "artifacts/layer_c_energy.json",
    "artifacts/layer_d_patterns.json",
    "artifacts/energy_summary/hints.json",
    "artifacts/event_inference/events.machine.json",
    "artifacts/event_inference/events.ml.json",
    "artifacts/symbolic_transcription/drum_events.json",
]

DENSE = {
    "artifacts/essentia/fft_bands.json",
    "artifacts/essentia/rms_loudness.json",
    "artifacts/essentia/loudness_envelope.json",
}
TARGET_FRAMES = 60


def decimate(doc: dict) -> dict:
    frames = doc.get("frames")
    if not isinstance(frames, list) or len(frames) <= TARGET_FRAMES:
        return doc
    n = len(frames)
    step = max(1, n // (TARGET_FRAMES - 1))
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    doc["frames"] = [frames[i] for i in idx]
    if isinstance(doc.get("metadata"), dict):
        doc["metadata"]["total_frames_original"] = n
        doc["metadata"]["decimated_for_fixture"] = True
    return doc


def copy_song(src_name: str, out_name: str, *, drop: set[str] = frozenset()):
    src = SRC_ANALYSIS / src_name
    dst = OUT / out_name
    if dst.exists():
        shutil.rmtree(dst)
    for rel in NEEDED:
        if rel in drop:
            continue
        s = src / rel
        if not s.exists():
            print(f"  skip (absent): {rel}")
            continue
        d = dst / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        if rel in DENSE:
            doc = json.loads(s.read_text())
            d.write_text(json.dumps(decimate(doc)))
        elif rel.endswith("layer_b_symbolic.json"):
            # the Symbolic Phrases lane only reads `phrase_windows`; the 4k-entry
            # `note_events` array is 3.5 MB of dead weight in a fixture.
            doc = json.loads(s.read_text())
            if isinstance(doc.get("note_events"), list):
                doc["note_events"] = doc["note_events"][:40]
            d.write_text(json.dumps(doc))
        else:
            shutil.copy2(s, d)
    print(f"  wrote {out_name}")


def copy_test_song():
    src = SRC_ANALYSIS / "_test_song"
    dst = OUT / "_test_song"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    # drop bulk the UI never loads (stems, midi transcription, reference dumps).
    for junk in ("artifacts/stems",
                 "artifacts/symbolic_transcription/basic_pitch",
                 "artifacts/symbolic_transcription/omnizart",
                 "reference/moises"):
        p = dst / junk
        if p.exists():
            shutil.rmtree(p)
    for md in dst.rglob("*.md"):
        md.unlink()
    for mid in dst.rglob("*.mid"):
        mid.unlink()
    for wav in dst.rglob("*.wav"):
        wav.unlink()
    # decimate the synthetic dense arrays too, if present
    for rel in ("artifacts/essentia/fft_bands.json",
                "artifacts/essentia/rms_loudness.json",
                "artifacts/essentia/loudness_envelope.json"):
        p = dst / rel
        if p.exists():
            p.write_text(json.dumps(decimate(json.loads(p.read_text()))))
    print("  wrote _test_song")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_SONGS.mkdir(parents=True, exist_ok=True)
    print("building fixtures:")
    copy_song(REG_SOURCE, "RegFull - Fixture")
    copy_song(REG_SOURCE, "RegPartial - Fixture",
              drop={"artifacts/essentia/fft_bands.json"})
    copy_test_song()
    # audio: ship the real mp3 for RegFull (real decode path). RegPartial reuses
    # it; _test_song intentionally has none.
    mp3 = SRC_SONGS / f"{REG_SOURCE}.mp3"
    if mp3.exists():
        shutil.copy2(mp3, OUT_SONGS / "RegFull - Fixture.mp3")
        shutil.copy2(mp3, OUT_SONGS / "RegPartial - Fixture.mp3")
        print("  copied mp3 for RegFull + RegPartial")
    else:
        print("  WARNING: source mp3 not found:", mp3)


if __name__ == "__main__":
    main()
