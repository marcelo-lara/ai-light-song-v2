from __future__ import annotations

import argparse
import json
import sys

from . import candidates, export, features, groundtruth, harness
from .paths import GOLD_SONGS, all_songs, cache_path


def _songs(args) -> list[str]:
    if args.songs:
        return args.songs
    return GOLD_SONGS if args.gold else all_songs()


def cmd_cache(args) -> None:
    for song in _songs(args):
        exists = cache_path(song).exists()
        if exists and not args.rebuild:
            print(f"  cached  {song}")
            continue
        feat = features.load(song, rebuild=True)
        print(f"  built   {song}  {feat.duration:7.1f}s  {len(feat.t)} frames  {len(feat.beats)} beats")


def cmd_gt(args) -> None:
    for song in _songs(args):
        seqs = groundtruth.load_sequences(song)
        if not seqs:
            continue
        print(f"\n{song}: {len(seqs)} drop sequence(s)")
        for seq in seqs:
            lo, hi = seq.span
            durs = {p: round(e - s, 3) for p, (s, e) in seq.phases.items()}
            print(f"   impact {seq.impact:8.3f}  span {lo:7.2f}-{hi:7.2f}  durs {durs}")
            for warning in seq.warnings:
                print(f"      ! non-contiguous: {warning}")


def cmd_propose(args) -> None:
    scores = []
    dump = {}
    for song in _songs(args):
        feat = features.load(song)
        props = candidates.propose(feat, per_channel=args.per_channel, spacing=args.spacing)
        dump[song] = props
        gt = groundtruth.impacts(song)
        if gt:
            scores.append(harness.score_song(song, gt, [p["time"] for p in props], args.tol))
        else:
            print(f"  {song:<34} unlabelled, {len(props)} candidates")
    if scores:
        harness.report(scores, title=f"stage 1 proposals (per_channel={args.per_channel})", tol=args.tol)
    if args.out:
        with open(args.out, "w") as handle:
            json.dump(dump, handle, indent=1)
        print(f"\n  wrote {args.out}")


def cmd_diag(args) -> None:
    """For each labelled impact, where does its beat rank inside each channel?

    This is the question stage 1 has to answer: if no channel ranks the true
    impact near the top, no threshold or re-ranker downstream can recover it.
    """
    import numpy as np

    for song in _songs(args):
        gt = groundtruth.impacts(song)
        if not gt:
            continue
        feat = features.load(song)
        times, table = candidates.beat_table(feat)
        chans = candidates.channels(table)
        print(f"\n{song}  ({len(times)} beats)")
        for g in gt:
            i = int(np.argmin(np.abs(times - g)))
            print(f"  impact {g:8.2f} -> beat {times[i]:8.2f} ({times[i]-g:+.2f}s)")
            ranks = []
            for name, score in sorted(chans.items()):
                order = candidates.nms_order(times, score, args.spacing)
                hit = next((r for r, j in enumerate(order, 1)
                            if abs(times[j] - g) <= args.window), None)
                ranks.append((hit if hit is not None else 10**6, name, len(order),
                              float(score[i])))
            for rank, name, total, value in sorted(ranks):
                shown = "-" if rank == 10**6 else f"{rank}"
                flag = "  <<<" if rank <= 3 else ""
                print(f"       {name:<12} event rank {shown:>4}/{total:<4} score {value:8.2f}{flag}")


def cmd_localize(args) -> None:
    """Oracle test of stage 3 alone: hand it a region centred on the true impact
    and see whether it recovers the instant. Isolates localisation error from
    region-proposal error."""
    import numpy as np

    errs = []
    for song in _songs(args):
        gt = groundtruth.impacts(song)
        if not gt:
            continue
        feat = features.load(song)
        print(f"\n{song}")
        for g in gt:
            for offset in (-args.jitter, 0.0, args.jitter):
                got = candidates.localize(feat, g + offset, radius=args.radius,
                                          leading_edge=args.leading_edge)
                errs.append(got - g)
                print(f"  impact {g:8.2f}  region centre {g + offset:8.2f} -> {got:8.2f}  err {got - g:+.3f}s")
    if errs:
        a = np.abs(errs)
        print(f"\n  localisation |err| median={np.median(a):.3f}s max={np.max(a):.3f}s  "
              f"within 0.5s: {(a <= 0.5).sum()}/{len(a)}")


def cmd_export(args) -> None:
    print("writing draft proposals to data/analysis/<song>/reference/proposals/")
    for song in _songs(args):
        path = export.export_song(song, top=args.top, per_channel=args.per_channel)
        print(export.summary_line(song, path))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="drop_detection")
    parser.add_argument("--songs", nargs="*", default=None)
    parser.add_argument("--gold", action="store_true", help="restrict to the 4 labelled tracks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("cache"); p.add_argument("--rebuild", action="store_true"); p.set_defaults(fn=cmd_cache)
    p = sub.add_parser("gt"); p.set_defaults(fn=cmd_gt)
    p = sub.add_parser("diag")
    p.add_argument("--spacing", type=float, default=8.0)
    p.add_argument("--window", type=float, default=1.0)
    p.set_defaults(fn=cmd_diag)
    p = sub.add_parser("export")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--per-channel", type=int, default=3)
    p.set_defaults(fn=cmd_export)
    p = sub.add_parser("localize")
    p.add_argument("--radius", type=float, default=2.5)
    p.add_argument("--jitter", type=float, default=1.5)
    p.add_argument("--leading-edge", type=float, default=1.0)
    p.set_defaults(fn=cmd_localize)
    p = sub.add_parser("propose")
    p.add_argument("--per-channel", type=int, default=3)
    p.add_argument("--spacing", type=float, default=8.0)
    p.add_argument("--tol", type=float, default=harness.TOLERANCE)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_propose)

    args = parser.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
