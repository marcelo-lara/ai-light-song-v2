"""Experiment queue runner — regenerate every enabled experiment's
`reference/proposals/<name>.json` for one song or the whole corpus.

Run as `python -m experiments.run_queue` or via the `./experiment` wrapper.

`src/` never imports this module (the sandbox rule is `src/` -> `experiments/`,
not the reverse); importing `analyzer.config` here for song discovery is the
allowed direction.

D10.1: the runner executes inside the `app` container, so each `command` runs as
a plain subprocess in the current environment — not `docker compose run`. Only
`image = "app"` rows are honored; any other image is recorded skipped with a
reason.

Failure isolation: a non-zero exit, an unusable image, or a bad row is recorded
as failed(code) / skipped(reason) and the run continues. The process exits
non-zero only when every attempted (experiment x song) pair failed.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

try:  # py3.11+ stdlib; the dev image is 3.10 and ships tomli (same API)
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from analyzer.config import build_song_paths, discover_song_files

QUEUE_PATH = Path(__file__).resolve().parent / "queue.toml"
_STDERR_TAIL_LINES = 20


class QueueError(Exception):
    """Unrecoverable queue-runner setup error (bad/missing queue.toml)."""


def load_queue(queue_path: Path | None = None) -> list[dict]:
    queue_path = queue_path or QUEUE_PATH
    if not queue_path.exists():
        raise QueueError(f"queue.toml not found: {queue_path}")
    data = tomllib.loads(queue_path.read_text(encoding="utf-8"))
    rows = data.get("experiment", [])
    if not isinstance(rows, list) or not rows:
        raise QueueError(f"queue.toml has no [[experiment]] rows: {queue_path}")
    for row in rows:
        for field in ("name", "command", "image", "enabled"):
            if field not in row:
                raise QueueError(f"queue.toml row missing '{field}': {row!r}")
    return rows


def substitute(template: str, mapping: dict[str, str]) -> list[list[str]]:
    """Tokenise `template` (splitting ` && ` into stages) then substitute
    placeholders per-token, so a value with spaces stays a single argument."""
    stages: list[list[str]] = []
    for part in template.split("&&"):
        part = part.strip()
        if not part:
            continue
        tokens = [mapping.get(tok.strip("{}"), tok) if tok.startswith("{") and tok.endswith("}")
                  else tok for tok in shlex.split(part)]
        stages.append(tokens)
    return stages


def _run_stages(stages: list[list[str]], cwd: Path) -> tuple[int, str]:
    """Run each stage in order; stop at the first non-zero. Returns
    (returncode, stderr tail)."""
    for tokens in stages:
        completed = subprocess.run(
            tokens, cwd=cwd, capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            tail = "\n".join((completed.stderr or "").splitlines()[-_STDERR_TAIL_LINES:])
            return completed.returncode, tail
    return 0, ""


def _iter_songs(args: argparse.Namespace) -> list[tuple[str, Path, Path]]:
    """Return (song_name, analysis_dir, song_path) triples."""
    out: list[tuple[str, Path, Path]] = []
    if args.song:
        paths = build_song_paths(args.song, args.analysis_root)
        out.append((paths.song_name, paths.song_output_dir, paths.song_path))
    else:
        for song_path in discover_song_files(args.analysis_root, args.songs_root):
            paths = build_song_paths(str(song_path), args.analysis_root)
            out.append((paths.song_name, paths.song_output_dir, paths.song_path))
    return out


def _validate_args(args: argparse.Namespace) -> None:
    if bool(args.song) == bool(args.all_songs):
        raise QueueError("Pass exactly one of --song or --all-songs.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experiments.run_queue",
        description="Regenerate every enabled experiment's reference/proposals/ lane for a song.",
    )
    parser.add_argument("--song")
    parser.add_argument("--all-songs", action="store_true")
    parser.add_argument("--analysis-root", default="/data/analysis")
    parser.add_argument("--songs-root")
    parser.add_argument("--only", help="comma-separated experiment names to restrict the run to")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]

    try:
        _validate_args(args)
        rows = load_queue()
        songs = _iter_songs(args)
    except QueueError as exc:
        print(f"[run_queue] {exc}", file=sys.stderr)
        return 2

    only = {n.strip() for n in args.only.split(",") if n.strip()} if args.only else None
    if only:
        rows = [r for r in rows if r["name"] in only]
        missing = only - {r["name"] for r in rows}
        for name in sorted(missing):
            print(f"[run_queue] --only names unknown experiment: {name}", file=sys.stderr)

    results: list[tuple[str, str, str]] = []  # (experiment, song, outcome)
    for row in rows:
        name = row["name"]
        for song_name, analysis_dir, song_path in songs:
            if not row["enabled"]:
                results.append((name, song_name, "skipped(disabled)"))
                continue
            if row["image"] != "app":
                results.append((
                    name, song_name,
                    f"skipped(needs image {row['image']} — run ./experiment from the host)",
                ))
                continue
            stages = substitute(row["command"], {
                "song_name": song_name,
                "analysis_dir": str(analysis_dir),
                "song_path": str(song_path),
            })
            code, tail = _run_stages(stages, cwd=repo_root)
            if code == 0:
                results.append((name, song_name, "ok"))
            else:
                if tail:
                    print(f"--- {name} / {song_name} failed({code}) ---\n{tail}", file=sys.stderr)
                results.append((name, song_name, f"failed({code})"))

    _print_summary(results)

    attempted = [o for _, _, o in results if o == "ok" or o.startswith("failed(")]
    if attempted and all(o.startswith("failed(") for o in attempted):
        return 1
    return 0


def _print_summary(results: list[tuple[str, str, str]]) -> None:
    print("\n=== experiment queue summary ===")
    if not results:
        print("(nothing to run)")
        return
    width = max(len(f"{e} x {s}") for e, s, _ in results)
    ok = failed = skipped = 0
    for exp, song, outcome in results:
        print(f"  {f'{exp} x {song}':<{width}}  ->  {outcome}")
        if outcome == "ok":
            ok += 1
        elif outcome.startswith("failed("):
            failed += 1
        else:
            skipped += 1
    print(f"  {ok} ok, {failed} failed, {skipped} skipped ({len(results)} pairs)")


if __name__ == "__main__":
    raise SystemExit(main())
