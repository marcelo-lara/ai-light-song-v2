# CLAP voiceness — contrastive differential ("singing" vs "flute, synth")

*(CLAP audio-text model — reuses `experiments/clap/`'s audio tower and
two-centring formula; no new pin)*

**This candidate is an independent second opinion on the frame-level call,
not a boundary competitor.** CLAP's ~5s analysis window cannot time a phrase
edge — `vocal_phrase` spans are exported for the timeline and computed
against, but boundary F1 is reported, never scored, for this candidate.

## Status

**OPEN — built and running, kill condition unevaluable until item 1's ground
truth exists.** v3.5 item 5. `compute`/`export`/`score` all run green on the
full 5-song scoring corpus (`_test_song`, `ayuni`, `Hideaway - Kiesza`,
`Armin - Revolution`, `Titanium - David Guetta ft Sia`). Debugger lane
`5. CLAP Voiceness` wired in, under Human Hints. No song in this environment
carries `type: "vocal"` ground truth (same finding as items 3-4), so the kill
condition — "does not agree with the marked spans better than chance on
`ayuni`" — **cannot be evaluated: unevaluable, not passed or failed.**

## Why? What for?

Does a contrastive CLAP pair distinguish a sung phrase from a flute where
CLAP's own absolute vocal axis could not? `arrangement_state` reports
`vocals` present 40.8% of `ayuni` — the false-vocal question items 3-7 chase
from different angles; this one asks it via a perceptual-audio model instead
of DSP cues (item 4) or hand-built classifiers.

## Method

One contrastive pair — *"a person singing"* against *"a flute, a synth
lead"* — read as a differential after the two centrings
`experiments/clap/probes.py` established as mandatory (survey Measurement 5):
never a single absolute-sentence reading.

1. **Audio tower**: `experiments.clap.model.compute()`, called verbatim (same
   `laion/larger_clap_music`, `WINDOW_S=5.0`, `HOP_S=1.0`). No new GPU code.
2. **Text tower**: one forward pass over the two pair sentences
   (`model.py::text_embeddings`), CPU, same call shape as
   `experiments/clap/probes.py`'s own `text_embeddings`.
3. **Differential**: `model.py::differential()` — the exact two-centring
   formula from `probes.py`'s `axes()` (centre across sentences within a
   window, then z-score across time per sentence), generalised from that
   function's six built-in pairs to this one custom pair. The formula is
   copied rather than imported: `axes()` is wired to the module-level
   six-pair `PAIRS` dict, and reshaping that API for one caller was judged
   not worth it for four lines of arithmetic (documented as a resolved
   D-item — see the implementation report).
4. **Voiceness**: `sigmoid(z)` maps the (already per-song z-scored)
   differential onto `[0, 1]` as `voiceness_common.schema` requires.
   `confidence = |voiceness - 0.5| * 2`, the same decision-margin heuristic
   `vocal_voiceness` (item 4) uses — an honest heuristic, not a calibrated
   probability.
5. **`vocal_phrase` spans**: threshold at 0.5, merge gaps ≤1s (one hop),
   drop anything shorter than `MIN_PHRASE_S = 2.0` (a CLAP window is 5s wide;
   anything shorter is grid noise). Exported for the timeline and for
   `scorer.py`'s boundary bookkeeping — **never scored on boundary F1.**

## Grid — reported honestly, not upsampled

CLAP's own `HOP_S` is 1.0s. Frames are exported on that native grid
(`interval_ms: 1000` in the proposal, not the `50` other voiceness
candidates use) rather than resampled to a finer interval — upsampling would
imply a timing precision a 5s analysis window does not have (CLAUDE.md: "say
so rather than snapping and implying a precision that isn't there").

## Why this doesn't contradict `experiments/clap/`'s own "weak vocal axis" finding

`experiments/clap/README.md` (Measurement 1) found CLAP's `vocal` axis
**weak** (+0.36…+1.18 on three vocal outros) against the vocal stem's
unambiguous reading (+1.5, +1.6, +1.2), concluding "take voice presence from
the stems." **That measurement used a different pair** — `vocal` in
`experiments/clap/probes.py`'s six-axis survey is *"a singer singing a
melody, lead vocals in front"* vs *"purely instrumental music, nobody
singing"* — read as one of many axes pooled over allin1 section windows, in
an absolute (cross-song) framing for the character layer. This item asks a
narrower, sharper question with its own pair — singing specifically against
*pitched instruments that could be mistaken for it* (flute, synth lead),
which is the actual confusion `arrangement_state`'s stem-RMS false-vocal rate
is chasing — computed per-window on this experiment's own 5s/1s grid, still
read only as a differential (never absolute) per song. A weak reading on one
pair, on one axis-survey framing, is not evidence against a different pair
built for a different, narrower confusion. Whether it actually resolves that
confusion better is exactly what the (currently unevaluable) kill condition
would tell us.

## Results evidence

Scored against `voiceness_common`'s three incumbents via the shared scorer,
matched-budget (`bounds_per_min` reported beside every rate). **Scored
metrics: frame voiceness accuracy, false_vocal_rate. Boundary F1 is reported,
not scored, for `clap_voiceness`** (starred in the table).

Full 5-song scoring corpus:

| song | clap_voiceness (frame_acc / false_vocal_rate / bounds/min) | arrangement_state | vocal_phrases | mix_rms_baseline |
| --- | --- | --- | --- | --- |
| `_test_song` | 0.5091 / 0.4909 / 12.74 | 0.6213 / 0.3787 / 10.34 | 0.6170 / 0.3830 / 22.74 | 0.0465 / 0.9535 / 6.20 |
| `Hideaway - Kiesza` | 0.4274 / 0.5726 / 7.70 | 0.1657 / 0.8343 / 6.68 | 0.6818 / 0.3182 / 54.84 | 0.1599 / 0.8401 / 39.10 |
| `Armin - Revolution` | 0.5236 / 0.4764 / 4.99 | 0.3582 / 0.6418 / 5.57 | 0.7686 / 0.2314 / 55.68 | 0.0206 / 0.9794 / 10.52 |
| `Titanium - David Guetta ft Sia` | 0.4498 / 0.5502 / 6.77 | 0.2857 / 0.7143 / 5.16 | 0.7132 / 0.2868 / 46.48 | 0.0398 / 0.9602 / 18.59 |
| `ayuni` | 0.5031 / 0.4969 / 6.65 | 0.5918 / 0.4082 / 6.56 | 0.7551 / 0.2449 / 53.19 | 0.1235 / 0.8765 / 70.67 |
| **aggregate avg** | **0.4826 / 0.5174 / 7.77** | 0.4045 / 0.5955 / 6.86 | 0.7071 / 0.2929 / 46.59 | 0.0781 / 0.9219 / 29.02 |

Full output: [`out/score.txt`](out/score.txt) (measured this session, all 5
scoring-corpus songs).

**No ground truth exists yet** — checked directly, same finding as items 3-4:
every song in the scoring corpus has zero `type == "vocal"` rows in
`reference/human/human_hints.json` in this environment. So
`false_vocal_rate` against an empty marked-span set is mathematically
"fraction of frames this candidate calls voiced" — an honest proxy, flagged
`is_proxy_no_ground_truth` per row in `out/score.txt`, not the validated
metric. Re-running `score` after the operator marks spans on `ayuni`
recomputes the real number with no code change.

**Read the aggregate carefully.** `clap_voiceness`'s aggregate frame_accuracy
(0.4826) beats `arrangement_state` (0.4045) but trails `vocal_phrases`
(0.7071) — and every one of these numbers is proxy-only (against zero marked
spans, "accuracy" here still reduces to agreement with a threshold, not
correctness). No candidate should be read as "winning" from this table alone.

## Usage

```bash
# compute needs transformers/torch — the research sandbox image
# (ai-light-song-v2-research:dev), reusing experiments/clap/'s own launcher
./experiments/clap/run_in_container.sh \
    python -m experiments.clap_voiceness.run compute --song <name>

# export/score only read the cache/JSON compute wrote — plain app image
docker compose run --rm app python -m experiments.clap_voiceness.run export --song <name>
docker compose run --rm app python -m experiments.clap_voiceness.run score
```

`compute` runs one CLAP audio forward pass + one text forward pass per song
and caches the per-window differential under
`experiments/clap_voiceness/cache/`. `export` writes
`reference/proposals/clap_voiceness.json` via `voiceness_common.schema`.
`score` (no `--song` = the 5-song scoring corpus) writes `out/score.txt`.

## `queue.toml`

**Not run automatically by the queue runner.** `compute` requires
`transformers`, only installed in the research sandbox image, not the `app`
image the queue runner executes in — and the runner only ever honors
`image = "app"`, skipping the *whole* row otherwise
(`experiments/run_queue.py`, D10.1: "only `image = "app"` is honored... any
other value is recorded skipped(needs image X...), never run"). The
`queue.toml` row for this experiment uses a non-`app` image value
(`clap-research`) so it is recorded `skipped(needs image clap-research...)`
on every queue run, rather than either (a) claiming `image = "app"` and
failing `compute` for a missing `transformers`, or (b) silently never
appearing in the queue at all. This matches `experiments/clap/`'s own
precedent of staying out of `queue.toml` entirely for the same reason — this
item's row exists mainly so the queue's skip list documents *why* nothing
here ran. Both steps must be run manually, using the two commands under
Usage above.

## Conclusion

Built, green end-to-end on the full 5-song scoring corpus. Reuses
`experiments/clap/`'s audio tower and two-centring formula with no new model
or pin, on CLAP's own native ~1Hz grid (reported honestly, not upsampled).
The aggregate proxy table shows `clap_voiceness` between `arrangement_state`
and `vocal_phrases` on frame accuracy — **not a promotion candidate on
current evidence**, and with zero ground truth the kill condition ("does not
agree with the marked spans better than chance on `ayuni`") is explicitly
**unevaluable**, not passed or failed. Next step is the same one items 3-4
named: mark `type: "vocal"` spans on `ayuni`, then re-run `score` with no
code change.
