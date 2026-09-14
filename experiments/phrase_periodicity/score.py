"""Two measured outputs, both written to `out/score.txt` and reproduced by
`run score`:

  1. **phrase length** per song / stem — z-normalised vs the raw-envelope
     ablation (the named cheap baseline). Operator truth: `Chimera - Hana`
     bass = 8 bars "almost exact" (two stems must find it independently);
     `Hideaway` bass = 8 bars.
  2. **block regime** on `Queen of Kings` — predicted regime per operator block
     vs the marked regimes (refinement doc item 3 table).

Kill condition (docs/implementation-plan-v3.4.md item 7): prominence fails to
separate the known-8-bar songs (`Chimera - Hana`, `Hideaway` bass) from the
rest. Recorded pass/fail regardless.
"""
from __future__ import annotations

import numpy as np

from . import features as feat_mod
from . import paths
from . import periodicity as per

KNOWN_8BAR = ["Chimera - Hana", "Hideaway - Kiesza"]

# Queen of Kings marked regimes (refinement doc item 3). Matched by title
# substring against reference/human/human_hints.json.
QOK_REGIME_TRUTH = {
    "Fairytale like intro": "through-composed",
    "Melodic Vocal bridge": "through-composed",
    "Post-Intro": "bar-loop",
    "Post-Intro + Harmony": "bar-loop",
    "Main chorus section": "half-bar-loop",
    "Main chorus section (continues)": "half-bar-loop",
}


def _phrase_row(cache: dict, stem: str, znorm: bool) -> tuple[int | None, float]:
    key = f"{'z' if znorm else 'raw'}_{stem}"
    return per.phrase_length(cache[key])


def _phrase_section() -> list[str]:
    lines = ["PHRASE LENGTH — bar-sequence autocorrelation, period in bars", "=" * 70, ""]
    lines.append(f"  {'song / stem':<34}{'z-norm':>16}{'raw (ablation)':>20}")
    lines.append(f"  {'':<34}{'period  prom':>16}{'period  prom':>20}")
    kill_z: dict[str, float] = {}
    for song in paths.SONGS:
        cache = feat_mod.load_cache(song)
        for stem in paths.STEM_IDS:
            pz, promz = _phrase_row(cache, stem, True)
            pr, promr = _phrase_row(cache, stem, False)
            if stem == "bass":
                kill_z[song] = promz
            zc = f"{(str(pz) if pz else '—'):>6} {promz:+.3f}"
            rc = f"{(str(pr) if pr else '—'):>6} {promr:+.3f}"
            lines.append(f"  {song + ' / ' + stem:<34}{zc:>16}{rc:>20}")
        lines.append("")
    return lines, kill_z


def _kill_section(kill_z: dict[str, float]) -> list[str]:
    known = {s: kill_z[s] for s in KNOWN_8BAR if s in kill_z}
    rest = {s: v for s, v in kill_z.items() if s not in KNOWN_8BAR}
    lines = [
        "KILL CONDITION — prominence must separate the known-8-bar bass songs "
        "from the rest",
        "-" * 70,
    ]
    for s, v in sorted(kill_z.items(), key=lambda kv: -kv[1]):
        tag = " (known 8-bar)" if s in KNOWN_8BAR else ""
        lines.append(f"  bass z-norm prominence  {s:<34}{v:+.3f}{tag}")
    lo_known = min(known.values()) if known else float("nan")
    hi_rest = max(rest.values()) if rest else float("nan")
    passed = bool(known) and bool(rest) and lo_known > hi_rest
    lines.append("")
    lines.append(f"  min(known 8-bar) = {lo_known:+.3f}   max(rest) = {hi_rest:+.3f}")
    lines.append(
        f"  OUTCOME: {'PASS — prominence separates the known-8-bar songs' if passed else 'FAIL — prominence does not separate the known-8-bar songs; kill candidate'}"
    )
    lines.append("")
    return lines, passed


def _regime_section() -> list[str]:
    song = "Queen of Kings - Alessandra"
    cache = feat_mod.load_cache(song)
    starts = cache["block_starts"]
    ends = cache["block_ends"]
    titles = [str(t) for t in cache["block_titles"]]
    lines = ["BLOCK REGIME — Queen of Kings, predicted vs marked", "=" * 70, ""]
    lines.append(f"  {'block':<34}{'rep@bar':>9}{'rep@beat':>9}{'predicted':>16}{'truth':>16}")
    n_truth = n_hit = 0
    for s, e, title in zip(starts, ends, titles):
        # regime is judged on the composite (all four stems summed, re-z per
        # bar) — the rhythm carrier for a whole passage.
        bars = per.bars_in_span(cache, float(s), float(e), "z_composite")
        rb = per.rep_at_bar(bars)
        rbeat = per.rep_at_beat(bars)
        reg, _period = per.regime(bars)
        truth = QOK_REGIME_TRUTH.get(title, "")
        if truth:
            n_truth += 1
            n_hit += int(truth == reg)
        lines.append(
            f"  {title[:33]:<34}{rb:>9.2f}{rbeat:>9.2f}{reg:>16}{truth or '·':>16}"
        )
    lines.append("")
    lines.append(f"  regime agreement on marked blocks: {n_hit}/{n_truth}")
    lines.append("")
    return lines


def build_report() -> str:
    phrase_lines, kill_z = _phrase_section()
    kill_lines, _passed = _kill_section(kill_z)
    regime_lines = _regime_section()
    return "\n".join(phrase_lines + [""] + kill_lines + [""] + regime_lines)


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = build_report()
    (paths.OUT_ROOT / "score.txt").write_text(text + "\n")
    print(text)
