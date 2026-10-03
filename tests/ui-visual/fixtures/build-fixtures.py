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

v3.10 item 9: the files and fields the analyzer cut in item 8 (`genre.json`,
`hpcp.json`, `layer_a_harmonic.json`, `layer_c_energy.json`, the section
`key`/`energy`/`tension`/`rhythm` clue fields, `block_energy.json`,
`segments.seed.json`, the rhythm/energy/tension candidate-producer proposals)
are not copied and not injected. The one deliberate exception is
`reference/human/segments.json`'s legacy `energy`/`tension` keys on the first
`RegFull` row (`inject_segments`): the operator's file may still carry them,
and `removed-surfaces.spec.ts` asserts a segment save leaves them untouched.

`reference/human/lyric_validations.json` (v3.4 item 5) is also synthetic —
`RegFull` gets `validated_ids: [2, 3]` (the Moises word tokens "We" / "are"),
which `lyric-validation.spec.ts` asserts; the other two fixtures get an empty
list. The file must exist on every fixture so the song-load fetch never 404s
(the visual suite fails any run with a failed network response). Written by
`inject_lyric_validations` below.

Dense per-frame arrays (fft_bands / rms_loudness / loudness_envelope /
whisperx-vad) are decimated to ~60 evenly spaced frames, keeping the first
and last frame so the song's full duration is still represented. info.json /
beats.json are copied verbatim so full-extent checks stay meaningful.

`artifacts/whisperx-vad/whisperx_vad.json` (v3.6 item 2) is written by the
`whisperx` Compose service, run separately before this script — if
`Armin - Revolution`'s artifact does not exist yet, the copy is silently
skipped (see `copy_song`'s "skip (absent)" branch) and the WhisperX VAD lane
renders empty in the fixture until the service has been run once.
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
    "vocal_cadence.json",
    "beats.json",
    "sections.json",
    "song_event_timeline.json",
    "arrangement_state.json",
    "artifacts/section_segmentation/sections_display.json",
    "artifacts/gestures/song_event_timeline.json",
    "reference/human/human_hints.json",
    "reference/human/song_facts.json",
    "reference/moises/lyrics.json",
    "reference/moises/segments.json",
    "reference/proposals/character.json",
    "reference/proposals/allin1_posterior.json",
    "reference/proposals/stem_presence_sections.json",
    "reference/proposals/clap_events.json",
    "reference/proposals/kick_check.json",
    "reference/proposals/crash_check.json",
    "reference/proposals/phrases.json",
    "reference/proposals/section_names.json",
    "reference/proposals/vocal_transcription.json",
    "reference/proposals/vocal_phrases.json",
    "reference/proposals/reactive_bands.json",
    "reference/proposals/grid.json",
    "artifacts/whisperx-vad/whisperx_vad.json",
    "artifacts/essentia/fft_bands.json",
    "artifacts/essentia/fft_bands.bass.json",
    "artifacts/essentia/fft_bands.drums.json",
    "artifacts/essentia/fft_bands.harmonic.json",
    "artifacts/essentia/fft_bands.vocals.json",
    "artifacts/essentia/rms_loudness.json",
    "artifacts/essentia/loudness_envelope.json",
    "artifacts/section_segmentation/sections.json",
    "artifacts/symbolic_transcription/drum_events.json",
]

DENSE = {
    "artifacts/whisperx-vad/whisperx_vad.json",
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


def inject_segments(out_name: str, *, segments_json: list | None):
    """Write the synthetic operator `reference/human/segments.json`.

    `segments_json=None` means: do not write it at all (the "no operator
    segmentation yet" case). `RegFull` gets a 2-span file whose first row
    still carries legacy `energy`/`tension` keys (see the module docstring)."""
    if segments_json is None:
        return
    base = OUT / out_name / "reference/human"
    base.mkdir(parents=True, exist_ok=True)
    (base / "segments.json").write_text(json.dumps(segments_json, indent=2) + "\n")
    print(f"  wrote {out_name}/reference/human/segments.json")


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


def inject_block_reviews(out_name: str, *, reviewed: bool = False):
    """v3.7 item 1 — write the synthetic block_reviews.json.

    `RegFull - Fixture` gets four rows keyed against the `gestures` lane's
    real `song_event_timeline.json` starts (7.86, 9.288, 15.232) plus one
    `start` (999.999) that matches nothing in the current run — one `correct`,
    one `wrong`, one `misplaced`, and one stale row, per plan item 1's fixture
    requirement. The other fixtures get an empty `reviews` array — the file
    must still exist so the app's song-load fetch does not 404
    (ui-regression §3)."""
    hints_path = OUT / out_name / "reference/human/human_hints.json"
    song_name = REG_SOURCE
    if hints_path.exists():
        song_name = json.loads(hints_path.read_text()).get("song_name", REG_SOURCE)
    p = OUT / out_name / "reference/human/block_reviews.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    reviews = (
        [
            {
                "lane_id": "gestures",
                "start": 7.86,
                "verdict": "correct",
                "reason": None,
                "note": "",
                "reviewed_at": "2026-09-19T14:00:00Z",
            },
            {
                "lane_id": "gestures",
                "start": 9.288,
                "verdict": "wrong",
                "reason": "boundary",
                "note": "nothing here",
                "reviewed_at": "2026-09-19T14:01:00Z",
            },
            {
                "lane_id": "gestures",
                "start": 15.232,
                "verdict": "misplaced",
                "reason": "label",
                "note": "real event, wrong phase name",
                "reviewed_at": "2026-09-19T14:02:00Z",
            },
            {
                "lane_id": "gestures",
                "start": 999.999,
                "verdict": "correct",
                "reason": None,
                "note": "stale — no current block matches",
                "reviewed_at": "2026-09-19T14:03:00Z",
            },
        ]
        if reviewed
        else []
    )
    p.write_text(
        json.dumps(
            {"schema_version": "1.0", "song_name": song_name, "reviews": reviews},
            indent=2,
        )
        + "\n"
    )
    print(f"  wrote {out_name}/reference/human/block_reviews.json")


FIXTURE_FILTER_SWEEPS = [
    {"direction": "opening", "stem": "harmonic", "start_s": 8.0, "end_s": 24.0,
     "depth": 1.8, "confidence": 0.62},
    {"direction": "closing", "stem": "harmonic", "start_s": 96.0, "end_s": 108.0,
     "depth": 2.4, "confidence": 0.71},
    {"direction": "opening", "stem": "bass", "start_s": 150.0, "end_s": 160.0,
     "depth": 0.9, "confidence": 0.48},
]


def inject_filter_sweep(out_name: str, *, blocks: list | None):
    """v3.10 item 14 — `reference/proposals/filter_sweep.json`.

    `Armin - Revolution` (the RegFull/RegPartial source) has no detected sweep
    in the live corpus, which would leave the lane empty and the block-count
    check vacuous, so those two fixtures get the three hand-fixed rows in
    `FIXTURE_FILTER_SWEEPS` (synthetic, like `inject_block_reviews`).
    `_test_song` keeps its own real file (`blocks=None` = leave `copy_test_song`'s
    copy alone). The file must exist on every fixture (a 404 fails the suite).
    `filter-sweep.spec.ts` reads this file for its expected count."""
    if blocks is None:
        return
    p = OUT / out_name / "reference/proposals/filter_sweep.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "schema_version": "1.0",
        "song_name": REG_SOURCE,
        "generated_from": {"experiment": "experiments/filter_sweep", "synthetic_fixture": True},
        "blocks": blocks,
    }, indent=2) + "\n")
    print(f"  wrote {out_name}/reference/proposals/filter_sweep.json")


FIXTURE_VERDICT_EVIDENCE = {
    "stems": {"read": "bass and drums entries in section-007 and section-008",
              "showed": "bass and drums enter together at the start of section-007"},
    "drum_density": {"read": "drum_density across section-007 and section-008",
                     "showed": "dense through both sections, no thinning"},
    "dropouts": {"read": "dropouts before section-007",
                 "showed": "one short dropout ahead of section-007"},
    "loudness": {"read": "loudness of section-007 against the song",
                 "showed": "section-007 sits near the song's 75th percentile"},
    "web_search": {"read": "one query for the claim on this version",
                   "showed": "a fan wiki calls the chorus a drop, no second source"},
}


def inject_verdict_and_queue(out_name: str):
    """v3.11 item 24 — `reference/pre-analysis/verdict.json` and
    `reference/proposals/pending.json` for `RegFull - Fixture` only (synthetic).

    verdict.json: three section-evidence rows, one per outcome and
    non-overlapping (drops `refuted` 004-005, chorus_is_drop `unresolved`
    007-008, has_build_ups `confirmed` 010) plus a `bpm` row with no section
    evidence (no block). `drops` carries a settled second pass.
    pending.json: one pending `hint` and one pending `verdict_check` for
    `chorus_is_drop`. `RegPartial - Fixture` and `_test_song` get neither
    (the "no verdict.json -> no lane" case); `helpers.ts` tolerates the 404.
    `verdict-checks.spec.ts` snapshots and restores both files."""
    base = OUT / out_name / "reference"
    (base / "pre-analysis").mkdir(parents=True, exist_ok=True)
    (base / "proposals").mkdir(parents=True, exist_ok=True)
    verdict = {
        "schema_version": "3.1",
        "song_name": REG_SOURCE,
        "generated_from": {"hint": "reference/pre-analysis/structure.json",
                           "hint_schema_version": "1.1", "info": "info.json"},
        "version_check": {"version_mismatch": False, "duration_delta_s": 0.79,
                          "bpm_delta_pct": None},
        "verdicts": {
            "generated_from": {"sections": "sections.json"},
            "status": "evaluated",
            "reason": None,
            "fields": {
                "drops": {"verdict": "refuted", "evidence": {
                    "expected": 2, "drop_runs": 1,
                    "drop_section_ids": ["section-004", "section-005"]}},
                "has_build_ups": {"verdict": "confirmed", "evidence": {
                    "expected": True, "build_up_section_ids": ["section-010"]}},
                "chorus_is_drop": {"verdict": "unresolved", "evidence": {
                    "expected": True,
                    "drop_like_chorus_section_ids": ["section-007", "section-008"]}},
                "bpm": {"verdict": "confirmed", "evidence": {
                    "analysed_bpm": 129.41, "bpm_delta_pct": 0.3}},
            },
        },
        "second_pass": {"fields": {
            "drops": {
                "verdict": "refuted", "wrong": "hint",
                "evidence": {**FIXTURE_VERDICT_EVIDENCE, "web_search": None},
                "first_pass_verdict": "refuted", "operator": None},
            "chorus_is_drop": {
                "verdict": None, "wrong": None, "evidence": None,
                "first_pass_verdict": None, "operator": None},
        }},
    }
    (base / "pre-analysis" / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n")
    queue = {
        "schema_version": "1.0",
        "song_name": REG_SOURCE,
        "proposals": [
            {"id": "prop-hint-001", "type": "hint", "status": "pending",
             "created_at": "2026-10-01T10:00:00Z", "rejection_reason": None,
             "evidence": "impact with no covering hint",
             "hint": {"start": 100.0, "end": 108.0, "title": "Strobe on the impact",
                      "summary": "Impact-aligned strobe."}},
            {"id": "prop-check-001", "type": "verdict_check", "status": "pending",
             "created_at": "2026-10-01T10:01:00Z", "rejection_reason": None,
             "evidence": "the audio reads as a drop but the web names it a chorus",
             "verdict_check": {
                 "field": "chorus_is_drop",
                 "claim": "The chorus is a drop",
                 "evidence": FIXTURE_VERDICT_EVIDENCE,
                 "cannot_settle": "the audio fits a drop and a chorus equally; the web has one source",
                 "question": "Is the chorus of this recording also its drop?"}},
        ],
    }
    (base / "proposals" / "pending.json").write_text(json.dumps(queue, indent=2) + "\n")
    print(f"  wrote {out_name}/reference/pre-analysis/verdict.json + proposals/pending.json")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_SONGS.mkdir(parents=True, exist_ok=True)
    print("building fixtures:")
    copy_song(REG_SOURCE, "RegFull - Fixture")
    inject_lyric_validations("RegFull - Fixture", validated=True)
    inject_filter_sweep("RegFull - Fixture", blocks=FIXTURE_FILTER_SWEEPS)
    inject_block_reviews("RegFull - Fixture", reviewed=True)
    inject_verdict_and_queue("RegFull - Fixture")
    inject_segments(
        "RegFull - Fixture",
        segments_json=[
            {"start": 40, "end": 60, "label": "Build", "energy": 4, "tension": 2},
            {"start": 60, "end": 80, "label": "Drop"},
        ],
    )
    copy_song(REG_SOURCE, "RegPartial - Fixture",
              drop={"artifacts/essentia/fft_bands.json",
                    "artifacts/essentia/fft_bands.bass.json",
                    "artifacts/essentia/fft_bands.drums.json",
                    "artifacts/essentia/fft_bands.harmonic.json",
                    "artifacts/essentia/fft_bands.vocals.json"})
    inject_lyric_validations("RegPartial - Fixture")
    inject_filter_sweep("RegPartial - Fixture", blocks=FIXTURE_FILTER_SWEEPS)
    inject_block_reviews("RegPartial - Fixture")
    copy_test_song()
    # copy_test_song drops reference/moises; the Moises Lyrics lane fetches
    # lyrics.json on every song, so give _test_song RegFull's copy (a 404 would
    # fail assertNoRuntimeErrors — ui-regression §3.1).
    moises = OUT / "_test_song" / "reference" / "moises"
    moises.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT / "RegFull - Fixture" / "reference" / "moises" / "lyrics.json",
                 moises / "lyrics.json")
    inject_lyric_validations("_test_song")
    inject_block_reviews("_test_song")
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
