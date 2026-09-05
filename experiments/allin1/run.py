"""CLI for the allin1 experiment.

    # GPU step — needs the allin1 sandbox image
    ./experiments/allin1/run_in_container.sh python -m experiments.allin1.run cache

    # everything below reads the cache and runs anywhere
    python -m experiments.allin1.run export
    python -m experiments.allin1.run score
    python -m experiments.allin1.run show "Titanium - David Guetta ft Sia"

Commands
    cache    run allin1 over the corpus and cache its raw output
    cache-activations  cache the frame-level beat/segment/label activations
    export   write reference/proposals/allin1.json for every cached song
    score    the gold-set measurement, the labelling health table, the beat grid
    stability  re-run the model N times per gold song and diff the segmentations
    show     one song's derived sections and transitions, as text
"""
from __future__ import annotations

import json
import sys

from . import activations, export, features, model, score
from .paths import GOLD_SONGS, all_songs, out_file


def _songs(argv: list[str]) -> list[str]:
    return argv or all_songs()


def cmd_cache(argv: list[str]) -> int:
    songs = _songs(argv)
    failed = []
    for song in songs:
        try:
            data = model.load(song, rebuild="--rebuild" in argv)
            print(f"  allin1 {song:<40} {len(data['segments']):3d} segments  {data['bpm']} bpm", flush=True)
        except Exception as exc:                     # noqa: BLE001 — sandbox script
            failed.append(song)
            print(f"  FAIL   {song:<40} {type(exc).__name__}: {exc}"[:200], flush=True)
    if failed:
        print(f"\n{len(failed)} song(s) failed: {', '.join(failed)}")
        return 1
    return 0


def cmd_cache_activations(argv: list[str]) -> int:
    """The frame-level curves, which `cache` does not fetch.

    A separate command because it is a separate GPU pass and most of the
    experiment does not need it — only the character work does.
    """
    songs = _songs(argv)
    failed = []
    for song in songs:
        try:
            data = activations.load(song, rebuild="--rebuild" in argv)
            print(f"  acts  {song:<40} {data['label'].shape[1]:5d} frames @ "
                  f"{float(data['rate_hz']):.0f} Hz", flush=True)
        except Exception as exc:                     # noqa: BLE001 — sandbox script
            failed.append(song)
            print(f"  FAIL  {song:<40} {type(exc).__name__}: {exc}"[:200], flush=True)
    if failed:
        print(f"\n{len(failed)} song(s) failed: {', '.join(failed)}")
        return 1
    return 0


def cmd_export(argv: list[str]) -> int:
    songs = model.cached_songs(_songs(argv))
    if not songs:
        print("No cached allin1 runs. Run `cache` in the allin1 sandbox image first.")
        return 1
    for song in songs:
        path = export.export_song(song)
        print(export.summary_line(song, path))
    print(f"\nWrote {len(songs)} proposal file(s) to "
          f"data/analysis/<song>/reference/proposals/allin1.json")
    return 0


def cmd_score(argv: list[str]) -> int:
    songs = model.cached_songs(all_songs())
    missing = [s for s in GOLD_SONGS if s not in songs]
    if missing:
        print(f"Gold songs not cached: {', '.join(missing)}")
        return 1
    blocks = [score.gold_table(), score.corpus_table(songs), score.grid_table(songs)]
    text = "\n\n\n".join(blocks) + "\n"
    print(text)
    out_file("score.txt").write_text(text)
    print(f"(also written to {out_file('score.txt')})")
    return 0


def cmd_stability(argv: list[str]) -> int:
    """Run the model repeatedly on the same audio and diff what comes back.

    Needs the allin1 sandbox image — it calls the model, not the cache. The
    first corpus run of this experiment came back different from an earlier one
    on 14 of 21 songs, which is a promotion blocker under the determinism rule, so
    the size of the disagreement is measured rather than assumed.
    """
    repeats = 3
    rest = []
    for arg in argv:
        if arg.startswith("--repeats="):
            repeats = int(arg.split("=", 1)[1])
        else:
            rest.append(arg)
    songs = rest or GOLD_SONGS

    entries = []
    for song in songs:
        runs = []
        for _ in range(repeats):
            derived = features.derive(song, model.compute(song))
            runs.append(derived["sections"])
        boundaries = [[s["start_s"] for s in rows[1:]] for rows in runs]
        union = sorted({round(b, 1) for run in boundaries for b in run})
        matched = sum(
            1 for b in union
            if all(any(abs(b - x) <= 0.5 for x in run) for run in boundaries)
        )
        entry = {
            "song": song,
            "repeats": repeats,
            "label_sequences": [[s["name"] for s in rows] for rows in runs],
            "boundaries": boundaries,
            "boundary_agreement": {"matched": matched, "union": len(union)},
        }
        entries.append(entry)
        print(f"  {song:<40} {[len(r) for r in runs]} sections per run  "
              f"{matched}/{len(union)} boundaries in every run", flush=True)

    out_file("stability.json").write_text(json.dumps(entries, indent=2) + "\n")
    print()
    print(score.stability_table(entries))
    return 0


def cmd_show(argv: list[str]) -> int:
    if not argv:
        print("usage: show <song>")
        return 1
    song = argv[0]
    derived = features.derive(song, model.load(song))
    lab = derived["labelling"]
    print(f"{song}   {derived['tempo']['bpm']} bpm   "
          f"{derived['bar_grid']['bar_count']} bars   labelling: {lab['status']}")
    if lab["reason"]:
        print(f"  ! {lab['reason']}")
    print()
    impacts = features.human_impacts(song)
    for section in derived["sections"]:
        marks = [f"{i:.2f}" for i in impacts
                 if section["start_s"] - 0.6 <= i <= section["start_s"] + 0.6]
        print(f"  {section['start_s']:8.2f} - {section['end_s']:8.2f}  {section['name']:<12}"
              f" bars {str(section['start_bar']):>4} +{section['bars']:<3}"
              f" phrases {section['phrase_count']}"
              + (f"   <== human impact {', '.join(marks)}" if marks else ""))
    print()
    for t in derived["transitions"]:
        near = [f"{i:.2f}" for i in impacts if abs(i - t["time_s"]) <= 0.5]
        print(f"  {t['time_s']:8.2f}  {t['pair']:<22} {t['kind']:<8}"
              f" beat {t['essentia_beat_offset_s']:+.3f}s"
              f" {'downbeat' if t['on_downbeat'] else '        '}"
              + (f"   <== impact {', '.join(near)}" if near else ""))
    return 0


COMMANDS = {
    "cache": cmd_cache,
    "cache-activations": cmd_cache_activations,
    "export": cmd_export,
    "score": cmd_score,
    "stability": cmd_stability,
    "show": cmd_show,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 1
    return COMMANDS[argv[0]]([a for a in argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
