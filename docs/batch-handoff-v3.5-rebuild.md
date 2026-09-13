# Batch handoff — v3.5 corpus rebuild, rescore and calibration

> **TEMPORARY DOCUMENT. Delete it in the commit that completes task 7.**
> It exists to hand one bounded worklist to one batch session. It is not a
> record of anything — every durable finding it produces belongs in
> `docs/experiments.md`, `docs/issues.md` or an experiment's own `README.md`,
> never here. Do not let it become a status file.

Read [`CLAUDE.md`](../CLAUDE.md) first. The rules below are the ones this
worklist trips over most; `CLAUDE.md` is authoritative where they differ.

## Hard rules for this worklist

- **Docker only.** Nothing runs on the host — no `pip`, no `python`, no `npm`.
  Every command below is already a container invocation; do not "simplify" one
  by running it directly.
- **Never push.** Commit locally. The branch is `refinement-v3.1`.
- **No silent fallbacks.** A missing input fails loudly or emits `unknown`. If
  a step cannot run, record why and move to the next task — never substitute a
  plausible value to keep a run green.
- **Never tune a threshold to make a number look good.** This is the single
  easiest way to ruin this worklist. See task 5's STOP.
- **Do not archive, delete or promote anything.** Promotion into `src/` and
  the decision to kill an experiment are the operator's, always. Report and
  stop.
- **`src/` never imports from `experiments/`.**
- **Determinism.** Same input + engine version produces byte-identical output.
  If a rerun produces a different artifact, that is a defect to report, not
  noise to smooth over.

## Why this rebuild exists

The operator asked for every experiment to be recomputed across every song
before any keep/kill decision, because judging experiments on proposal files
computed weeks apart under different code compares cache dates as much as
methods. **Do not shortcut it by reusing an existing proposal file.**

## State at handoff (2026-09-13)

Corpus is 23 songs under `data/analysis/`. Rebuild already complete:

| experiment | proposals rebuilt |
| --- | --- |
| `texture_novelty` | 23/23 |
| `phrase_periodicity` | 23/23 |
| `structural_vs_micro` | 23/23 |
| `whisperx_vad` | 23/23 |
| `vocal_voiceness` | 4/23 — **in flight**, may already be done |
| `svd_tagger` | 19/23 — **in flight** |
| `singer_identity` | 9/23 — **in flight**, on the fixed k gate |

Three background jobs were running when this was written. **Task 1 is to
confirm whether they finished**, not to assume either way.

Scoreable voiceness corpus is **5 songs**: `ayuni`, `Cinderella - Ella Lee`,
`Armin - Revolution`, `In da name of love - Anita and Ray`,
`What a Feeling - Courtney Storm`. Every hint on those five is classified;
`docs/experiments.md` "Vocal ground truth inventory" says what each contains.
Other songs have unclassified hints and the scorer fails loud on them — that
is correct behaviour, not a bug to fix.

---

## Task 1 — finish the rebuild

Check what is actually on disk, per experiment:

```bash
cd /home/darkangel/ai-light-song-v2
for n in texture_novelty phrase_periodicity structural_vs_micro vocal_voiceness \
         whisperx_vad svd_tagger singer_identity; do
  echo "$n: $(find data/analysis -name "$n.json" -newer experiments/queue.toml | wc -l)/23"
done
```

Any experiment below 23/23 needs its remaining songs computed. Song names are
the directory names under `data/analysis/` (they contain spaces — always
quote them).

App-image experiments (`texture_novelty`, `phrase_periodicity`,
`structural_vs_micro`, `vocal_voiceness`) — the queue runner does all four:

```bash
docker compose run --rm app ./experiment --all-songs
```

It is safe to re-run: it recomputes rows it has already done. It prints
nothing until it exits (Python buffers stdout when not a TTY), so redirect to
a log and watch the proposal counts above instead of the terminal.

Sandbox-image experiments run one song at a time, `compute` then `export`:

```bash
# svd_tagger — its own image, CPU
./experiments/svd_tagger/run_in_container.sh \
    python -m experiments.svd_tagger.run compute --song "<song>"
docker compose run --rm app python -m experiments.svd_tagger.run export --song "<song>"

# singer_identity — its own Compose service, CPU
docker compose run --rm --no-deps -T singer-identity \
    python -m experiments.singer_identity.run compute --song "<song>"
docker compose run --rm app python -m experiments.singer_identity.run export --song "<song>"
```

`singer_identity`'s `compute` reads `experiments/whisperx_vad/cache/<song>.npz`
and never recomputes VAD. whisperX is already rebuilt for all 23, so that
ordering constraint is satisfied — but if you ever rebuild whisperX again,
`singer_identity` must be recomputed after it.

**Machine limits.** 16 cores, 30 GB RAM, one GTX 1650 with 4 GB. Every compute
above is CPU by default. Do not run more than three of these jobs at once —
load hits 16 with three and everything slows together.

**Success:** all seven at 23/23. Do not commit — proposal files are gitignored
(`data/analysis/*/**`), which is why nothing in this task produces a commit.

## Task 2 — republish `arrangement_state` across the corpus

The promoted `vocals_phrase` field in each song's top-level
`arrangement_state.json` is fused from `reference/proposals/whisperx_vad.json`,
which task 1 rebuilt. Every song's published file is therefore stale.

```bash
docker compose run --rm app ./analyze --song "/data/songs/<song>.mp3" \
    --stage publish-arrangement-state
```

for each of the 23 songs. The stage fails loudly if
`artifacts/arrangement_state.json` or `artifacts/essentia/fft_bands.vocals.json`
is missing — if that happens for a song, record the song and move on; do not
synthesise the input.

**Success:** every `data/analysis/*/arrangement_state.json` newer than its
song's `reference/proposals/whisperx_vad.json`. Nothing to commit (gitignored).

## Task 3 — rescore every experiment

```bash
for e in texture_novelty phrase_periodicity structural_vs_micro vocal_voiceness \
         whisperx_vad svd_tagger singer_identity; do
  docker compose run --rm app python -m "experiments.$e.run" score
done
```

Each writes `experiments/<name>/out/score.txt`, which **is** tracked and **is**
the durable evidence.

Expect the numbers to move from what `docs/experiments.md` currently records.
Two reasons, both legitimate: the scorer was rewritten to three classes
(positive / residual / negative / unknown, residual excluded from
precision/recall), and the scoreable corpus grew from 3 songs to 5. **Report
movement, do not explain it away.** A candidate that got worse got worse.

If the scorer raises on a song, read the error. `ValueError: hint ids are
neither type: "vocal" nor classified` means that song's hints are undeclared —
that is an operator task, never guessable. Record the song and the hint ids
and move on.

**Then update `docs/experiments.md`**: every items 4-7 results table gets the
new numbers, each table stating it was measured against the current
three-class scorer on the 5-song corpus. This closes the `docs/issues.md`
entry "Items 4-7 voiceness numbers predate the three-class scorer…" — delete
that entry in the same commit (the issues file is a queue, not a history).

**Commit:** `Rescore items 4-7 on the rebuilt corpus and three-class scorer`.

## Task 4 — item 6, `svd_tagger` per-song rescale

The one cheap experiment that would settle item 6. Measured finding already
recorded in `docs/experiments.md`: SVD **discriminates well** (AUC 0.907 on
`ayuni`, 0.937 on `Cinderella - Ella Lee`) but is **miscalibrated by roughly
5x**, so its raw score never crosses the shared threshold and the published
series reads as all-zero.

Rescale per song (e.g. divide by the song's own high percentile, the way
`arrangement_state` derives a per-song threshold rather than a global one),
then rescore. The question is narrow: **does a per-song rescale alone make
SVD competitive, given the AUC says the ranking is already good?**

Write the answer into `docs/experiments.md`'s item 6 section and
`experiments/svd_tagger/README.md`. Keep item 6's status honest — it is
currently "OPEN — no promotion case, but not a kill either", and it stays open
unless this measurement changes that.

**Do not promote it and do not archive it** regardless of the result.

**Commit:** `6. SVD Tagger — per-song rescale, measured`.

## Task 5 — `singer_identity` calibration report

```bash
docker compose run --rm app python -m experiments.singer_identity.run calibrate
```

Reports, for each of the 11 songs in
`experiments/singer_identity/singer_ground_truth.json`: declared `lead_voices`
vs predicted `k`, the winning silhouette, the max centroid similarity, and the
`singer_change` count and rate per minute.

Background: `model.py`'s `_cluster()` used to seed `best_score = 0.0` and
compare `score > best_score`, which made **k=1 unreachable** — across the
corpus k was `{2: 19, 3: 3, 4: 1}`, never 1. Every solo song got a phantom
second cluster and flapped between the phantoms: `Titanium` (one singer)
emitted 39 change points at 10.1/min, while the corpus's one real duet emitted
2. That is fixed; `SILHOUETTE_FLOOR = 0.1` and `MERGE_SIMILARITY = 0.5` now
gate the split, and this report is how they get judged.

### STOP — the one thing not to do

`MERGE_SIMILARITY` and `SILHOUETTE_FLOOR` are **documented starting points,
deliberately not tuned.** If the report shows them mispredicting, **report the
mismatch and stop.** Do not search for values that make 11 songs come out
right — that is fitting to the ground truth, it would make every subsequent
number meaningless, and the project's standing rule forbids tuning a candidate
until a number looks acceptable.

Re-deriving k at a different threshold does **not** need a recompute: the cache
now stores `embeddings`, `embedded_window_index`, `centroid_similarity` and
`silhouette`, so a *reported* sensitivity sweep ("k would match ground truth at
MERGE_SIMILARITY in [x, y]") is cheap and is genuinely useful to the operator.
Producing that sweep as evidence is welcome. **Changing the shipped constants
on the strength of it is the operator's call.**

Write the report table into `experiments/singer_identity/README.md`'s "Results
evidence" section (it currently holds em-dash placeholders) and summarise it in
`docs/experiments.md`'s "Singer Identity" section.

**Commit:** `8. Singer Identity — calibration against declared singer counts`.

## Task 6 — full validation

```bash
docker compose run --rm test
docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test
docker compose run --rm ui npm run test
docker compose run --rm ui npm run build
```

Baselines at handoff: **153 analyzer tests pass**; **MCP smoke 11/11** with
`get_song_overview` at 5499 bytes (budget is 6 KB — if a change pushes it over,
that is a real regression, not a budget to raise); **394 UI tests pass with one
pre-existing `App.test.tsx` failure** that is already on this branch and is not
yours.

If MCP snapshots need regenerating, it must go through the `test` service —
the `mcp` container mounts read-only and fails with `OSError: [Errno 30]`:

```bash
docker compose run --rm -e MCP_REGEN_SNAPSHOTS=1 test \
    python -m pytest mcp/tests/test_overview.py mcp/tests/test_detail.py -q
```

Regenerate only when a deliberate change made a snapshot wrong. A snapshot
diff you did not intend is a defect to investigate.

## Task 7 — close out

Delete this file. Commit that deletion together with a short summary comment
in whichever commit lands last.

---

## What to bring back to the operator, not decide

1. **The by-ear review** in [`issues.md`](issues.md) — "`arrangement_state`'s
   `vocals` channel is still an RMS-only claim". Four spans, listened to in the
   debugger against the audio. No session may perform or waive it.
2. **Keep/kill on `singer_identity` and `svd_tagger`.** Report the numbers.
   The operator resists fast kill recommendations and wants per-song behaviour
   and what an experiment uniquely produces weighed first — `singer_change` is
   the only duet/handoff signal anything in this pipeline produces.
3. **Any threshold change** (task 5's STOP).
4. **Unclassified hints** on songs outside the 5-song scoreable set. Declared
   data, never guessed.
