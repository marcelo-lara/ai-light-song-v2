"""Entry point for the song-dynamics model survey.

    ./experiments/drop_detection/research/run_in_container.sh \
        python -m experiments.drop_detection.research.run <cmd>

Commands
    cache       compute + cache MERT, CLAP and beat-this for the gold songs
    cache-all   the same over the whole corpus
    cache-allin1 allin1 over the whole corpus (run in the allin1 sandbox image)
    downbeats   are the human impacts on a downbeat, and whose downbeat?
    layers      which MERT layer gives the best structural boundaries
    boundaries  boundary quality of every candidate representation
    probe       CLAP text-probe behaviour around the human impacts
    narrate     the whole song read back as CLAP z-scores, 5 s at a time
    vocab       which CLAP sentences respond consistently to a drop
    dynamics    continuous tension / intensity curves, checked at the impacts
    hybrid      learned regions + the existing stem localiser, scored at +-0.5 s
    corpus      allin1 label quality across all 21 songs
    describe    one row per section: allin1 function + MERT identity + CLAP texture
    identity    does repetition-aware labelling recognise a returning chorus
"""
from __future__ import annotations

import json
import sys

import numpy as np

from . import beatgrid, clap, mert, structure
from .common import (GOLD_SONGS, all_songs, essentia_grid, gold_impacts,
                     hit_rate, nearest_error, out_file)

TOLS = (0.5, 1.0, 2.0)


# ----------------------------------------------------------------- caching --


def cmd_cache_allin1(songs: list[str]) -> None:
    """Runs in the allin1 sandbox image only."""
    from . import allinone

    for song in songs:
        try:
            data = allinone.load(song)
            print(f"  allin1 {song}  {len(data['segments'])} segments")
        except Exception as exc:                        # noqa: BLE001 - survey script
            print(f"  FAIL   {song}  {type(exc).__name__}: {exc}"[:160])


def cmd_cache(songs: list[str]) -> None:
    model = mert._load_model()
    for song in songs:
        mert.load(song, model=model, rebuild=True)
        print(f"  mert   {song}")
    del model
    import torch

    torch.cuda.empty_cache()

    bundle = clap._load()
    for song in songs:
        clap.load(song, bundle=bundle, rebuild=True)
        print(f"  clap   {song}")
    del bundle
    torch.cuda.empty_cache()

    bt = beatgrid._load()
    for song in songs:
        beatgrid.load(song, model=bt, rebuild=True)
        print(f"  beats  {song}")


# --------------------------------------------------------------- downbeats --


def cmd_downbeats() -> None:
    rows = []
    for song, impacts in gold_impacts().items():
        ess = essentia_grid(song)
        bt = beatgrid.load(song)
        for imp in impacts:
            rows.append({
                "song": song,
                "impact": imp,
                "essentia_beat": nearest_error(ess.beats, [imp])[0],
                "essentia_downbeat": nearest_error(ess.downbeats, [imp])[0],
                "beatthis_beat": nearest_error(bt["beats"], [imp])[0],
                "beatthis_downbeat": nearest_error(bt["downbeats"], [imp])[0],
            })
    print(f"{'song':<32} {'impact':>8} {'ess beat':>9} {'ess bar':>9} {'bt beat':>9} {'bt bar':>9}")
    for r in rows:
        print(f"{r['song']:<32} {r['impact']:8.2f} {r['essentia_beat']:+9.3f} "
              f"{r['essentia_downbeat']:+9.3f} {r['beatthis_beat']:+9.3f} {r['beatthis_downbeat']:+9.3f}")
    for key in ("essentia_beat", "essentia_downbeat", "beatthis_beat", "beatthis_downbeat"):
        errs = np.abs([r[key] for r in rows])
        print(f"  {key:<20} median |err| {np.median(errs):.3f}s   "
              f"within 0.1s {int((errs <= 0.1).sum())}/{len(errs)}   "
              f"within 0.25s {int((errs <= 0.25).sum())}/{len(errs)}")
    out_file("downbeats.json").write_text(json.dumps(rows, indent=1))


# ------------------------------------------------------------------ layers --


def cmd_layers() -> None:
    gold = gold_impacts()
    print("MERT layer sweep: boundary recall against the 7 human impacts\n")
    header = f"{'layer':>5} " + " ".join(f"{'+-'+str(t):>7}" for t in TOLS) + f" {'bounds/min':>11}"
    print(header)
    for layer in range(13):
        hits = {t: 0 for t in TOLS}
        total = 0
        per_min = []
        for song, impacts in gold.items():
            data = mert.load(song)
            emb = data["beat_emb"][layer].astype(np.float32)
            bounds, _ = structure.boundaries(emb, data["beats"])
            minutes = (data["beats"][-1] - data["beats"][0]) / 60.0
            per_min.append(len(bounds) / max(minutes, 1e-6))
            for t in TOLS:
                hits[t] += hit_rate(bounds, impacts, t)[0]
            total += len(impacts)
        cells = " ".join(f"{hits[t]}/{total:<5}" for t in TOLS)
        print(f"{layer:>5} {cells} {np.mean(per_min):11.2f}")


# -------------------------------------------------------------- boundaries --


def _pipeline_boundaries(song: str) -> np.ndarray:
    from .common import ANALYSIS_ROOT

    path = ANALYSIS_ROOT / song / "sections.json"
    rows = json.loads(path.read_text())
    return np.array([float(r["start"]) for r in rows[1:]])


def _librosa_boundaries(song: str) -> np.ndarray:
    """Classical baseline: beat-synchronous CQT + the same novelty machinery."""
    import librosa

    from .common import load_audio

    y = load_audio(song, 22050)
    grid = essentia_grid(song)
    cqt = np.abs(librosa.cqt(y=y, sr=22050, hop_length=512, n_bins=84))
    times = librosa.frames_to_time(np.arange(cqt.shape[1]), sr=22050, hop_length=512)
    idx = np.searchsorted(times, grid.beats)
    edges = np.concatenate([idx, [cqt.shape[1]]])
    sync = np.stack([
        cqt[:, edges[i]:max(edges[i] + 1, edges[i + 1])].mean(axis=1) for i in range(len(grid.beats))
    ])
    sync = librosa.amplitude_to_db(sync.T, ref=np.max).T
    return structure.boundaries(sync, grid.beats)[0]


def _clap_beat_sync(cl: dict[str, np.ndarray], beats: np.ndarray) -> np.ndarray:
    emb = cl["audio_emb"].astype(np.float32)
    idx = np.clip(np.searchsorted(cl["times"], beats), 0, len(emb) - 1)
    return emb[idx]


def _candidates(song: str, *, per_minute: float = 4.0) -> dict[str, np.ndarray]:
    data = mert.load(song)
    cl = clap.load(song)
    beats = data["beats"]
    kw = {"per_minute": per_minute}
    out: dict[str, np.ndarray] = {}
    for layer in (2, 6, 9):
        emb = data["beat_emb"][layer].astype(np.float32)
        out[f"mert L{layer}"] = structure.boundaries(emb, beats, **kw)[0]
    stacked = np.concatenate([data["beat_emb"][l].astype(np.float32) for l in (2, 4, 6, 8)], axis=1)
    out["mert L2+4+6+8"] = structure.boundaries(stacked, beats, **kw)[0]

    out["clap novelty"] = structure.pick_boundaries(clap.semantic_novelty(cl), cl["times"], **kw)
    out["clap ssm"] = structure.boundaries(_clap_beat_sync(cl, beats), beats, **kw)[0]

    mert_nov = structure.multiscale_novelty(data["beat_emb"][2].astype(np.float32))
    clap_nov = structure.multiscale_novelty(_clap_beat_sync(cl, beats))
    n = min(len(mert_nov), len(clap_nov), len(beats))

    def unit(x):
        return (x - x.min()) / (x.max() - x.min() + 1e-9)

    out["mert+clap"] = structure.pick_boundaries(
        unit(mert_nov[:n]) + unit(clap_nov[:n]), beats[:n], **kw)

    out["pipeline sections"] = _pipeline_boundaries(song)
    out["librosa CQT"] = _librosa_boundaries(song)
    return out


def cmd_boundaries() -> None:
    gold = gold_impacts()
    agg: dict[str, dict] = {}
    for song, impacts in gold.items():
        cands = _candidates(song)
        print(f"\n== {song}  impacts {[round(i,2) for i in impacts]}")
        for name, bounds in cands.items():
            errs = nearest_error(bounds, impacts)
            row = agg.setdefault(name, {"hits": {t: 0 for t in TOLS}, "n": 0, "count": 0, "minutes": 0.0})
            for t in TOLS:
                row["hits"][t] += sum(1 for e in errs if abs(e) <= t)
            row["n"] += len(impacts)
            row["count"] += len(bounds)
            row["minutes"] += (bounds[-1] - bounds[0]) / 60.0 if len(bounds) > 1 else 0.0
            print(f"   {name:<18} n={len(bounds):<3} nearest err "
                  + ", ".join(f"{e:+.2f}" for e in errs))
    print(f"\n{'representation':<18} " + " ".join(f"{'+-'+str(t):>9}" for t in TOLS) + f" {'bounds/min':>11}")
    for name, row in agg.items():
        cells = " ".join(f"{row['hits'][t]}/{row['n']:<7}" for t in TOLS)
        print(f"{name:<18} {cells} {row['count']/max(row['minutes'],1e-6):11.2f}")


def cmd_sweep() -> None:
    """Recall against boundary budget. Precision cannot be measured — only the
    seven impacts are labelled, and a song has far more real boundaries than
    that — so the budget column *is* the precision axis: how many boundaries the
    representation is allowed to spend to catch them."""
    gold = gold_impacts()
    budgets = (1.5, 2.0, 3.0, 4.0, 6.0)
    table: dict[str, dict[float, tuple[int, int, int]]] = {}
    for budget in budgets:
        for song, impacts in gold.items():
            for name, bounds in _candidates(song, per_minute=budget).items():
                cell = table.setdefault(name, {}).setdefault(budget, (0, 0, 0))
                errs = nearest_error(bounds, impacts)
                table[name][budget] = (
                    cell[0] + sum(1 for e in errs if abs(e) <= 0.5),
                    cell[1] + sum(1 for e in errs if abs(e) <= 1.0),
                    cell[2] + sum(1 for e in errs if abs(e) <= 2.0),
                )
    print("hits out of 7, as +-0.5 / +-1.0 / +-2.0 s, per boundary budget\n")
    print(f"{'representation':<18} " + " ".join(f"{b:>14}/min" for b in budgets))
    for name, row in table.items():
        print(f"{name:<18} " + " ".join(f"{row[b][0]}/{row[b][1]}/{row[b][2]:<12}" for b in budgets))


# ------------------------------------------------------------------- probe --


SHORT = {p: s for p, s in zip(clap.PROMPTS, [
    "intro", "verse", "chorus", "breakdown", "outro",
    "build-up", "drop", "sparse", "full-groove",
    "vocals", "instrumental",
    "beat", "no-beat",
])}


def cmd_probe() -> None:
    """z-scored CLAP prompt response around each labelled impact."""
    for song, impacts in gold_impacts().items():
        cl = clap.load(song)
        z = clap.zscored(cl)
        t = cl["times"]
        print(f"\n== {song}")
        for imp in impacts:
            before = (t >= imp - 10) & (t < imp - 1)
            after = (t > imp + 1) & (t <= imp + 10)
            deltas = [(SHORT[p], float(z[after, i].mean() - z[before, i].mean()),
                       float(z[before, i].mean()), float(z[after, i].mean()))
                      for i, p in enumerate(clap.PROMPTS)]
            deltas.sort(key=lambda r: -abs(r[1]))
            print(f"  impact {imp:7.2f}   " + "   ".join(
                f"{name}: {b:+.2f}->{a:+.2f}" for name, d, b, a in deltas[:5]))


def cmd_narrate() -> None:
    """The whole song as a CLAP z-score read, one line per 5 s. This is the
    artifact to judge: would an LD recognise the song from it?"""
    for song, impacts in gold_impacts().items():
        cl = clap.load(song)
        z = clap.zscored(cl)
        t = cl["times"]
        role = z[:, :5]
        dyn = z[:, 5:9]
        print(f"\n== {song}   impacts {[round(i, 1) for i in impacts]}")
        step = int(round(5.0 / clap.HOP_S))
        for i in range(0, len(t), step):
            window = slice(i, i + step)
            r = role[window].mean(0)
            d = dyn[window].mean(0)
            mark = " <<< IMPACT" if any(t[i] <= imp < t[min(i + step, len(t) - 1)] for imp in impacts) else ""
            print(f"  {t[i]:6.1f}  role={SHORT[clap.PROMPT_GROUPS['role'][int(r.argmax())]]:<10}"
                  f" dyn={SHORT[clap.PROMPT_GROUPS['dynamics'][int(d.argmax())]]:<12}"
                  f" voc={z[window, 9].mean():+.2f} beat={z[window, 11].mean():+.2f}{mark}")


def cmd_vocab() -> None:
    """Which sentences actually respond to a drop, ranked by consistency.

    Seven labelled impacts against 26 prompts is not enough to *fit* anything,
    but it is enough to reject: a prompt whose sign flips across the seven is
    not describing the gesture, whatever its name says.
    """
    window_s = float(sys.argv[2]) if len(sys.argv) > 2 else clap.WINDOW_S
    bundle = clap._load("cpu")
    deltas: dict[str, list[float]] = {p: [] for p in clap.PROMPT_BANK}
    pre_level: dict[str, list[float]] = {p: [] for p in clap.PROMPT_BANK}
    # The window is `window_s` long and `t` holds its *centre*, so "before" has
    # to stop a full half-window short of the impact or it contains the drop.
    # Getting this wrong is the easiest way to manufacture a result here.
    guard = window_s / 2.0
    print(f"window {window_s:g}s, before/after guarded by {guard:g}s\n")
    for song, impacts in gold_impacts().items():
        t, z = clap.bank_response(song, bundle=bundle, window_s=window_s)
        for imp in impacts:
            before = (t >= imp - guard - 8) & (t <= imp - guard)
            after = (t >= imp + guard) & (t <= imp + guard + 8)
            for i, prompt in enumerate(clap.PROMPT_BANK):
                deltas[prompt].append(float(z[after, i].mean() - z[before, i].mean()))
                pre_level[prompt].append(float(z[before, i].mean()))
    rows = []
    for prompt, values in deltas.items():
        arr = np.array(values)
        agree = max(int((arr > 0).sum()), int((arr < 0).sum()))
        rows.append((agree, abs(float(arr.mean())), prompt, float(arr.mean()),
                     float(np.mean(pre_level[prompt]))))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    print(f"{'sign agree':>10} {'mean d':>8} {'pre z':>7}  prompt")
    for agree, _, prompt, mean, pre in rows:
        print(f"{agree:>7}/7 {mean:+8.2f} {pre:+7.2f}  {prompt[:70]}")


def cmd_dynamics() -> None:
    """Continuous curves, and whether they behave the way a light show needs.

    `tension` should be high in the bars leading into an impact and collapse
    after it; `intensity` should step up across it. Reported as the percentile
    of the song's own distribution, which is the form a cue-authoring model
    would consume."""
    bundle = clap._load("cpu")
    tension_prompts = [
        "a build-up with a rising riser and a snare roll, tension increasing",
        "a long filter sweep rising towards something",
        "a snare roll speeding up before an explosion",
    ]
    intensity_prompts = [
        "a dense wall of sound, everything playing at once",
        "a steady groove holding at full energy",
        "a strong four on the floor kick drum and a driving beat",
    ]
    quiet_prompts = [
        "a quiet sparse passage with very little going on",
        "the arrangement thinning out, instruments dropping away",
        "no drums at all, only sustained sounds",
    ]
    prompts = tension_prompts + intensity_prompts + quiet_prompts
    window_s = float(sys.argv[2]) if len(sys.argv) > 2 else clap.WINDOW_S
    guard = window_s / 2.0
    print(f"window {window_s:g}s\n")
    print(f"{'song':<32} {'impact':>8} {'tension pct':>12} {'intensity pct':>14} "
          f"{'d intensity':>12} {'d tension':>10}")
    for song, impacts in gold_impacts().items():
        t, z = clap.bank_response(song, prompts, bundle=bundle, window_s=window_s)
        tension = z[:, :3].mean(1)
        intensity = z[:, 3:6].mean(1) - z[:, 6:].mean(1)
        for imp in impacts:
            before = (t >= imp - guard - 8) & (t <= imp - guard)
            after = (t >= imp + guard) & (t <= imp + guard + 8)
            pct = lambda curve, mask: float((curve < curve[mask].mean()).mean() * 100)
            print(f"{song:<32} {imp:8.2f} {pct(tension, before):12.0f} "
                  f"{pct(intensity, after):14.0f} "
                  f"{intensity[after].mean() - intensity[before].mean():+12.2f} "
                  f"{tension[after].mean() - tension[before].mean():+10.2f}")


def cmd_describe() -> None:
    """The synthesis: one row per section, carrying everything three models
    know about it. This is the shape the artifact would take.

      function   from allin1  — what part of the song this is
      identity   from MERT    — which other sections are the same part
      texture    from CLAP    — how it should look, in words
    """
    from . import allinone

    bundle = clap._load("cpu")
    payload = {}
    for song, impacts in gold_impacts().items():
        data = mert.load(song)
        beats = data["beats"]
        emb = np.concatenate([data["beat_emb"][l].astype(np.float32) for l in (2, 4, 6, 8)], axis=1)
        labels = structure.segment_labels(emb, n_types=5)
        t, z = clap.bank_response(song, bundle=bundle)

        try:
            segments = allinone.load(song)["segments"]
        except FileNotFoundError:
            print(f"== {song}: no allin1 cache")
            continue

        merged: list[dict] = []
        for seg in segments:
            if seg["end"] - seg["start"] < 0.5:
                continue
            if merged and merged[-1]["label"] == seg["label"]:
                merged[-1]["end"] = seg["end"]
            else:
                merged.append(dict(seg))

        print(f"\n== {song}")
        rows = []
        for seg in merged:
            span = (beats >= seg["start"]) & (beats < seg["end"])
            ids = labels[span[:len(labels)]]
            identity = int(np.bincount(ids).argmax()) if len(ids) else -1
            mask = (t >= seg["start"]) & (t < seg["end"])
            if mask.any():
                order = np.argsort(z[mask].mean(0))[::-1]
                top = [clap.PROMPT_BANK[i] for i in order[:2]]
                bottom = [clap.PROMPT_BANK[i] for i in order[-1:]]
            else:
                top, bottom = [], []
            marks = [i for i in impacts if seg["start"] - 1.0 <= i <= seg["start"] + 1.5]
            rows.append({"start": seg["start"], "end": seg["end"], "function": seg["label"],
                         "identity": identity, "is": top, "is_not": bottom})
            print(f"  {seg['start']:7.2f}-{seg['end']:7.2f}  {seg['label']:<7} id={identity}  "
                  f"{'; '.join(s[:38] for s in top)}"
                  + ("   <<< human impact" if marks else ""))
        payload[song] = rows
    out_file("described.json").write_text(json.dumps(payload, indent=1))


def cmd_corpus() -> None:
    """Label quality of allin1 across the whole corpus.

    A functional segmentation is only useful if the labels vary. A song read as
    nine consecutive `intro` segments has boundaries but no function, and the
    artifact must be able to say so rather than write `intro` nine times.
    """
    from . import allinone

    print(f"{'song':<38} {'segs':>5} {'runs':>5} {'kinds':>6} {'top share':>10}  labels")
    degenerate = []
    for song in all_songs():
        try:
            data = allinone.load(song)
        except FileNotFoundError:
            continue
        segments = [s for s in data["segments"] if s["end"] - s["start"] > 0.5]
        labels = [s["label"] for s in segments]
        runs = [labels[0]] if labels else []
        for a, b in zip(labels, labels[1:]):
            if a != b:
                runs.append(b)
        kinds = sorted(set(labels))
        share = max((labels.count(k) for k in kinds), default=0) / max(len(labels), 1)
        flag = ""
        if len(kinds) <= 2 or share >= 0.8:
            degenerate.append(song)
            flag = "  <-- degenerate"
        print(f"{song:<38} {len(segments):>5} {len(runs):>5} {len(kinds):>6} {share:>10.2f}  "
              f"{','.join(kinds)}{flag}")
    print(f"\ndegenerate on {len(degenerate)} songs: {', '.join(degenerate)}")


def cmd_hybrid() -> None:
    """Learned region proposal + the existing stem-based instant localiser.

    The two halves were built for each other without knowing it: the harness's
    stage 3 (`candidates.localize`) already places an instant on the beat grid
    given a region, and its measured weakness was stage 1's regions. So this
    asks the only question that matters — if the region comes from allin1 or
    MERT instead of the level-change channel bank, does the final instant land
    inside the 0.5 s tolerance?
    """
    from .. import candidates, features
    from . import allinone

    print(f"{'song':<32} {'impact':>8} {'source':<12} {'region':>8} {'after localize':>15} {'err':>7}")
    totals = {"raw": [0, 0], "localized": [0, 0]}
    for song, impacts in gold_impacts().items():
        feat = features.load(song)
        data = mert.load(song)
        proposals = {
            "allin1": np.array([t for t, _, _ in allinone.transitions(allinone.load(song))]),
            "allin1-seg": allinone.boundaries(allinone.load(song)),
            "mert L2": structure.boundaries(data["beat_emb"][2].astype(np.float32), data["beats"])[0],
        }
        for name, bounds in proposals.items():
            for imp in impacts:
                if len(bounds) == 0:
                    continue
                region = float(bounds[int(np.argmin(np.abs(bounds - imp)))])
                if abs(region - imp) > 2.5:
                    continue
                placed = candidates.localize(feat, region)
                totals["raw"][0] += abs(region - imp) <= 0.5
                totals["raw"][1] += 1
                totals["localized"][0] += abs(placed - imp) <= 0.5
                totals["localized"][1] += 1
                print(f"{song:<32} {imp:8.2f} {name:<12} {region - imp:+8.2f} "
                      f"{placed - imp:+15.2f} {'HIT' if abs(placed - imp) <= 0.5 else '':>7}")
    for key, (hit, n) in totals.items():
        print(f"  {key:<10} within 0.5s: {hit}/{n}")


# ---------------------------------------------------------------- identity --


def cmd_identity() -> None:
    for song, impacts in gold_impacts().items():
        data = mert.load(song)
        beats = data["beats"]
        emb = np.concatenate([data["beat_emb"][l].astype(np.float32) for l in (4, 6, 8, 10)], axis=1)
        labels = structure.segment_labels(emb, n_types=5)
        runs = structure.label_runs(labels, beats)
        print(f"\n== {song}")
        for start, end, cid in runs:
            marks = [f"IMPACT {i:.2f}" for i in impacts if start - 0.5 <= i <= end]
            print(f"   {start:7.2f} - {end:7.2f}  cluster {cid}   {' '.join(marks)}")
        at_impact = []
        for imp in impacts:
            hit = [cid for start, end, cid in runs if start - 1.0 <= imp <= start + 1.0]
            at_impact.append(hit[0] if hit else None)
        print(f"   cluster entered at each impact: {at_impact}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "cache":
        cmd_cache(GOLD_SONGS)
    elif cmd == "cache-all":
        cmd_cache(all_songs())
    elif cmd == "cache-allin1":
        cmd_cache_allin1(all_songs())
    elif cmd == "downbeats":
        cmd_downbeats()
    elif cmd == "layers":
        cmd_layers()
    elif cmd == "boundaries":
        cmd_boundaries()
    elif cmd == "sweep":
        cmd_sweep()
    elif cmd == "probe":
        cmd_probe()
    elif cmd == "narrate":
        cmd_narrate()
    elif cmd == "vocab":
        cmd_vocab()
    elif cmd == "dynamics":
        cmd_dynamics()
    elif cmd == "hybrid":
        cmd_hybrid()
    elif cmd == "corpus":
        cmd_corpus()
    elif cmd == "describe":
        cmd_describe()
    elif cmd == "identity":
        cmd_identity()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
