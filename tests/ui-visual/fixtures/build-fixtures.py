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

`reference/human/block_energy.json` (v3.4 item 4) is likewise synthetic — it
rates the hand-curated hint-001 `{energy:5, tension:4}` and leaves hint-002 /
hint-003 unrated, which `block-energy-rating.spec.ts` asserts ("1 / 3 blocks
rated"). It is (re)written by `inject_block_energy` below.

`reference/human/lyric_validations.json` (v3.4 item 5) is also synthetic —
`RegFull` gets `validated_ids: [2, 3]` (the Moises word tokens "We" / "are"),
which `lyric-validation.spec.ts` asserts; the other two fixtures get an empty
list. The file must exist on every fixture so the song-load fetch never 404s
(the visual suite fails any run with a failed network response). Written by
`inject_lyric_validations` below.

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
    "arrangement_state.json",
    "reference/human/human_hints.json",
    "reference/human/song_facts.json",
    "reference/moises/lyrics.json",
    "reference/proposals/drop_impacts.json",
    "reference/proposals/character.json",
    "reference/proposals/vocal_transcription.json",
    "reference/proposals/vocal_phrases.json",
    "reference/proposals/reactive_bands.json",
    "reference/proposals/texture_novelty.json",
    "reference/proposals/phrase_periodicity.json",
    "reference/proposals/grid.json",
    "artifacts/essentia/fft_bands.json",
    "artifacts/essentia/fft_bands.bass.json",
    "artifacts/essentia/fft_bands.drums.json",
    "artifacts/essentia/fft_bands.harmonic.json",
    "artifacts/essentia/fft_bands.vocals.json",
    "artifacts/essentia/rms_loudness.json",
    "artifacts/essentia/loudness_envelope.json",
    "artifacts/layer_a_harmonic.json",
    "artifacts/layer_c_energy.json",
    "artifacts/section_segmentation/sections.json",
    "artifacts/symbolic_transcription/drum_events.json",
]

DENSE = {
    "artifacts/essentia/fft_bands.json",
    "artifacts/essentia/fft_bands.bass.json",
    "artifacts/essentia/fft_bands.drums.json",
    "artifacts/essentia/fft_bands.harmonic.json",
    "artifacts/essentia/fft_bands.vocals.json",
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
                 "artifacts/symbolic_transcription/omnizart",
                 "artifacts/allin1",
                 "artifacts/event_inference",
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
                "artifacts/essentia/fft_bands.bass.json",
                "artifacts/essentia/fft_bands.drums.json",
                "artifacts/essentia/fft_bands.harmonic.json",
                "artifacts/essentia/fft_bands.vocals.json",
                "artifacts/essentia/rms_loudness.json",
                "artifacts/essentia/loudness_envelope.json"):
        p = dst / rel
        if p.exists():
            p.write_text(json.dumps(decimate(json.loads(p.read_text()))))
    print("  wrote _test_song")


def inject_section_contest(out_name: str):
    """v3.4 item 3 — the `REG_SOURCE` song has no energy-contested section, so
    synthesize one: mark section-005 (a `chorus`) `function_status: "contested"`
    + `contested_by: "energy"` and switch the `sections.json` header the way
    `ui_data.apply_section_function_contest` does on a real contested song."""
    p = OUT / out_name / "sections.json"
    doc = json.loads(p.read_text())
    fs = doc["field_sources"]
    new_fs: dict = {}
    for k, v in fs.items():
        new_fs[k] = "section_function" if k == "function_status" else v
        if k == "function_status":
            new_fs["contested_by"] = "section_function"
    doc["field_sources"] = new_fs
    marked = False
    for s in doc["sections"]:
        if s.get("function") == "chorus" and not marked:
            s["function_status"] = "contested"
            s["contested_by"] = "energy"
            marked = True
    p.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"  patched {out_name}/sections.json — 1 contested section")


def inject_texture_novelty(out_name: str):
    """v3.4 item 6 — write a small deterministic texture_novelty.json (3 blocks
    / 2 interior boundaries) so `texture-novelty.spec.ts` can assert block edges
    against the ruler without depending on the experiment's real output. The
    experiment FAILED its kill condition; this lane is a one-review-pass
    audition surface. The file must exist on every fixture so the song-load
    fetch never 404s (the visual suite fails any run with a failed network
    response, ui-regression §3)."""
    hints_path = OUT / out_name / "reference/human/human_hints.json"
    song_name = REG_SOURCE
    if hints_path.exists():
        song_name = json.loads(hints_path.read_text()).get("song_name", REG_SOURCE)
    p = OUT / out_name / "reference/proposals/texture_novelty.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "song_name": song_name,
                "generated_from": {
                    "experiment": "experiments/texture_novelty",
                    "engine": "cosine self-similarity + Foote checkerboard novelty (1.0 s half-window)",
                    "feature_set": "raw 7-band MIX vector",
                },
                "blocks": [
                    {"start_s": 0.0, "end_s": 8.0, "edge_strength": None},
                    {"start_s": 8.0, "end_s": 20.0, "edge_strength": 0.71},
                    {"start_s": 20.0, "end_s": 32.0, "edge_strength": 0.46},
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"  wrote {out_name}/reference/proposals/texture_novelty.json")


def inject_phrase_periodicity(out_name: str):
    """v3.4 item 7 — write a small deterministic phrase_periodicity.json (3
    blocks: one through-composed with period null, one bar-loop, one
    half-bar-loop) so `phrase-periodicity.spec.ts` can assert the null-period
    "no phrase structure detected" string and block edges against the ruler
    without depending on the experiment's real output. The experiment PASSED
    its kill condition. The file must exist on every fixture so the song-load
    fetch never 404s (ui-regression §3)."""
    hints_path = OUT / out_name / "reference/human/human_hints.json"
    song_name = REG_SOURCE
    if hints_path.exists():
        song_name = json.loads(hints_path.read_text()).get("song_name", REG_SOURCE)
    p = OUT / out_name / "reference/proposals/phrase_periodicity.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "song_name": song_name,
                "generated_from": {
                    "experiment": "experiments/phrase_periodicity",
                    "engine": "per-bar 16-slot z-normalised energy profile -> bar-sequence autocorrelation (period only)",
                },
                "phrase_lengths": {
                    "bass": {"phrase_bars": 8, "prominence": 0.168, "detected": True},
                },
                "blocks": [
                    {"start_s": 0.0, "end_s": 8.0, "title": "Intro",
                     "regime": "through-composed", "period": None, "n_bars": 4},
                    {"start_s": 8.0, "end_s": 20.0, "title": "Groove",
                     "regime": "bar-loop", "period": 1.0, "n_bars": 6},
                    {"start_s": 20.0, "end_s": 32.0, "title": "Chorus",
                     "regime": "half-bar-loop", "period": 0.5, "n_bars": 6},
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"  wrote {out_name}/reference/proposals/phrase_periodicity.json")


def inject_block_energy(out_name: str, *, rated: bool = True):
    """v3.4 item 4 — write the synthetic block_energy.json.

    `RegFull - Fixture` gets hint-001 rated {energy:5, tension:4}, hint-002 /
    hint-003 left unrated (absent from `ratings`), so the panel header reads
    `1 / 3 blocks rated`. The other fixtures get an empty `ratings` array — the
    file must still exist so the app's song-load fetch does not 404 (the visual
    suite fails any run with a failed network response, ui-regression §3)."""
    hints = json.loads(
        (OUT / out_name / "reference/human/human_hints.json").read_text()
    )
    song_name = hints.get("song_name", REG_SOURCE)
    p = OUT / out_name / "reference/human/block_energy.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    ratings = (
        [{"hint_id": "hint-001", "energy": 5, "tension": 4}] if rated else []
    )
    p.write_text(
        json.dumps(
            {"schema_version": "1.0", "song_name": song_name, "ratings": ratings},
            indent=2,
        )
        + "\n"
    )
    print(f"  wrote {out_name}/reference/human/block_energy.json")


def inject_lyric_validations(out_name: str, *, validated: bool = False):
    """v3.4 item 5 — write the synthetic lyric_validations.json overlay.

    `RegFull - Fixture` gets `validated_ids: [2, 3]` (the Moises word tokens
    with id 2 / 3 in `reference/moises/lyrics.json`), which
    `lyric-validation.spec.ts` asserts render with the `moisesLyricsValidated`
    tint. The other fixtures get an empty list — the file must still exist so
    the app's song-load fetch does not 404 (ui-regression §3)."""
    hints_path = OUT / out_name / "reference/human/human_hints.json"
    song_name = REG_SOURCE
    if hints_path.exists():
        song_name = json.loads(hints_path.read_text()).get("song_name", REG_SOURCE)
    p = OUT / out_name / "reference/human/lyric_validations.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "song_name": song_name,
                "validated_ids": [2, 3] if validated else [],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"  wrote {out_name}/reference/human/lyric_validations.json")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_SONGS.mkdir(parents=True, exist_ok=True)
    print("building fixtures:")
    copy_song(REG_SOURCE, "RegFull - Fixture")
    inject_section_contest("RegFull - Fixture")
    inject_texture_novelty("RegFull - Fixture")
    inject_phrase_periodicity("RegFull - Fixture")
    inject_block_energy("RegFull - Fixture")
    inject_lyric_validations("RegFull - Fixture", validated=True)
    copy_song(REG_SOURCE, "RegPartial - Fixture",
              drop={"artifacts/essentia/fft_bands.json",
                    "artifacts/essentia/fft_bands.bass.json",
                    "artifacts/essentia/fft_bands.drums.json",
                    "artifacts/essentia/fft_bands.harmonic.json",
                    "artifacts/essentia/fft_bands.vocals.json"})
    inject_texture_novelty("RegPartial - Fixture")
    inject_phrase_periodicity("RegPartial - Fixture")
    inject_block_energy("RegPartial - Fixture", rated=False)
    inject_lyric_validations("RegPartial - Fixture")
    copy_test_song()
    inject_texture_novelty("_test_song")
    inject_phrase_periodicity("_test_song")
    inject_block_energy("_test_song", rated=False)
    inject_lyric_validations("_test_song")
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
