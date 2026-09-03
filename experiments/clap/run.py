"""CLI for the CLAP experiment.

    # GPU step — needs the research sandbox image
    ./experiments/clap/run_in_container.sh python -m experiments.clap.run cache

    # baseline features (audio, but no GPU) — same image
    ./experiments/clap/run_in_container.sh python -m experiments.clap.run cache-baseline

    # everything below reads the caches
    python -m experiments.clap.run character
    python -m experiments.clap.run hints
    python -m experiments.clap.run score
    python -m experiments.clap.run show "Titanium - David Guetta ft Sia"

Commands
    cache           CLAP audio embeddings over the corpus
    cache-baseline  MFCC + chroma over the identical windows
    character       write reference/proposals/character.json per song
    hints           score the character layer against the hand-marked hints
    score           identity AUC, boundary recall, catalog neighbours
    show            one song's identity read, as text
"""
from __future__ import annotations

import sys

from . import baselines, character_score, export_character, model, probes, score
from .paths import all_songs, out_file


def _songs(argv: list[str]) -> list[str]:
    return [a for a in argv if not a.startswith("--")] or all_songs()


def cmd_cache(argv: list[str]) -> int:
    songs = _songs(argv)
    bundle = model._load()
    failed = []
    for song in songs:
        try:
            data = model.load(song, rebuild="--rebuild" in argv, bundle=bundle)
            print(f"  clap  {song:<40} {data['emb'].shape[0]:4d} windows", flush=True)
        except Exception as exc:                     # noqa: BLE001 — sandbox script
            failed.append(song)
            print(f"  FAIL  {song:<40} {type(exc).__name__}: {exc}"[:200], flush=True)
    if failed:
        print(f"\n{len(failed)} song(s) failed: {', '.join(failed)}")
        return 1
    return 0


def cmd_cache_baseline(argv: list[str]) -> int:
    songs = _songs(argv)
    for song in songs:
        data = baselines.load(song, rebuild="--rebuild" in argv)
        print(f"  base  {song:<40} {data['mfcc'].shape[0]:4d} windows", flush=True)
    return 0


def cmd_character(argv: list[str]) -> int:
    songs = model.cached_songs(_songs(argv))
    if not songs:
        print("No cached CLAP embeddings. Run `cache` in the research image first.")
        return 1
    text_emb = probes.text_embeddings()
    for song in songs:
        path = export_character.export_song(song, text_emb)
        print(export_character.summary_line(song, path))
    print(f"\nWrote {len(songs)} file(s) to "
          f"data/analysis/<song>/reference/proposals/character.json")
    return 0


def cmd_hints(argv: list[str]) -> int:
    text = character_score.report(model.cached_songs(all_songs()))
    print(text)
    out_file("character.txt").write_text(text + "\n")
    print(f"(also written to {out_file('character.txt')})")
    return 0


def cmd_score(argv: list[str]) -> int:
    songs = model.cached_songs(all_songs())
    missing = [s for s in songs if s not in baselines.cached_songs(songs)]
    if missing:
        print(f"Baseline features not cached for: {', '.join(missing)}")
        return 1
    text = "\n\n\n".join([
        score.identity_table(songs),
        score.boundary_table(),
        score.catalog_table(songs),
    ]) + "\n"
    print(text)
    out_file("score.txt").write_text(text)
    print(f"(also written to {out_file('score.txt')})")
    return 0


def cmd_show(argv: list[str]) -> int:
    if not argv:
        print("usage: show <song>")
        return 1
    song = argv[0]
    from .paths import allin1_sections
    sections = allin1_sections(song)
    if not sections:
        print(f"{song}: no allin1 sections — run the allin1 experiment's export first.")
        return 1
    clap = model.load(song)
    vectors, rows = features.pool_sections(clap["times"], model.unit(clap["emb"]),
                                           sections, float(clap["window_s"]))
    letters = features.identity_letters(vectors)
    print(f"{song}\n")
    print(f"  {'window':<20}{'allin1':<12}{'CLAP':<6}{'windows':>8}")
    for section, row, letter in zip(sections, rows, letters):
        span = f"{section['start_s']:7.2f}-{section['end_s']:7.2f}"
        guard = "" if row["guarded"] else "  (unguarded)"
        print(f"  {span:<20}{section['name']:<12}{letter:<6}{row['windows']:>8}{guard}")
    print(f"\n  identity: {' '.join(letters)}")
    print(f"  allin1  : {' '.join(s['function'] for s in sections)}")
    return 0


COMMANDS = {
    "cache": cmd_cache,
    "cache-baseline": cmd_cache_baseline,
    "character": cmd_character,
    "hints": cmd_hints,
    "score": cmd_score,
    "show": cmd_show,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 1
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
