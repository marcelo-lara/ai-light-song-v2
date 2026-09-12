# WhisperX VAD — a speech-stack's VAD front-end over the vocal stem

*(whisperX 3.8.6's Pyannote-based VAD front-end — NEW sandbox image, NEW
checkpoint pin; diarization NOT attempted, VAD-only)*

**Does a speech-domain VAD find vocal-phrase edges on sung material, without
the confusions its own domain gap predicts?** The last candidate in the
false-vocal family (items 4-7), and the only one whose pretraining is on
*speech*, not music or a general audio-tagging class — built anyway so the
comparison happens by ear rather than by assumption.

## Status

**OPEN — built and running, kill condition unevaluable until item 1's ground
truth exists.** v3.5 item 7. All Python (`model.py`, `export.py`, `run.py`,
`score.py`), the `Dockerfile`, and `run_in_container.sh` are written, follow
`svd_tagger`'s (item 6) shape, and plug into the shared
`voiceness_common.schema`/`scorer`/`incumbents`. The VAD checkpoint was
pre-fetched and sha256-verified from the host **before** any Docker build was
attempted, applying item 6's own lesson (its in-build `curl` of a 327 MB file
stalled at ~154 KB/s and never completed) — this time the image built
successfully. `compute`/`export`/`score` ran green on the full 5-song scoring
corpus. Debugger lane `7. WhisperX VAD` wired in under Human Hints. No song in
this environment carries `type: "vocal"` ground truth (same finding as items
3-6), so the kill condition is unevaluable.

## Why? What for?

`arrangement_state` reports `vocals` present 40.8% of `ayuni` — the
false-vocal question items 3-7 chase from different angles. Items 4/5 use
hand-built DSP cues and a CLAP contrastive pair; item 6 asks whether a
general audio tagger's own `Singing` class does better. This item asks the
opposite-direction question: does a **speech-trained** VAD, built to find
"someone is talking" in call-center and meeting audio, transfer to "someone
is singing" at all — and if it does, is it cheap and reliable enough to be
worth the new image it costs?

## Three recorded objections — expected risks, not surprises

Per the product-refinement doc (`docs/product-refinement-v3.5.md`, §7), this
item is built anyway so these show up in the numbers rather than being
argued about in the abstract:

1. **Diarization answers *which speaker*, and on music it will assign a
   speaker to the flute.** It segments whatever its VAD accepts, so a
   diarization pass inherits exactly the false positives this whole release
   exists to remove — it does not fix the underlying confusion, it just adds
   a speaker label on top of it. This is also part of why diarization was
   not attempted here (see below) — even setting the token gate aside, a
   speaker split does not obviously help this item's actual question.
2. **The VAD is speech-trained: sustained sung vowels with no consonants are
   its classic miss, and pitched instruments its classic false accept.** A
   held vowel with no plosive/fricative texture looks acoustically closer to
   "silence" than "speech" to a model trained on conversational audio; a
   sustained lead synth or string pad can look closer to "speech" than a
   quiet vocal does.
3. **Lead-vs-backing is its weakest axis**, because double-tracked leads and
   harmony stacks overlap constantly and a binary VAD has no notion of
   "which voice" at all — this is a strictly weaker read than even the crude
   frame-level voiceness curves items 4-6 produce, since VAD's native output
   is a single yes/no per frame, not a continuous confidence that could later
   separate overlapping sources.

## Determinism — the automatic kill clause

**A candidate that needs a live token at analysis time cannot be promoted
regardless of its score.** This is stated plainly, per the refinement doc's
own instruction, rather than left to be discovered at the promotion gate.
whisperX's VAD checkpoint does not trigger this clause (see "Checkpoint" in
`model.py`'s docstring — it is bundled in the `whisperx` PyPI package itself,
not a gated Hugging Face download, and this experiment additionally pins its
own independently-verified copy, `COPY`'d into the image at build time, never
fetched at analysis time). Diarization's checkpoint
(`pyannote/speaker-diarization-3.1`) **does** trigger this clause — see
below.

## Diarization: not attempted

`echo $HF_TOKEN` and `~/.cache/huggingface/token` were both checked in this
environment before any code was written: **no Hugging Face token is
available.** `pyannote/speaker-diarization-3.1` is a gated checkpoint that
cannot be fetched, checksummed, or baked into an image without one. Per the
plan's own instruction ("if that is not achievable within this item's scope,
diarization is not attempted and the item ships VAD-only — say so plainly in
the README rather than discovering it at the promotion gate"), **diarization
was not built, not stubbed, and not attempted.** `export.py` does not emit a
diarization field with `null`s standing in for it — the schema does not
imply a capability the item does not have. If a token becomes available
later, adding the diarization pass is future work (see "Future work" below);
it needs its own build-secret-gated build (checkpoint fetched and
checksummed at image build time using a token supplied as a Docker build
secret, never fetched at analysis time) before it could even be attempted,
per the plan.

## Method

1. **whisperX's VAD front-end** (`whisperx.vads.pyannote.Pyannote`, wrapping
   a `pyannote.audio` `VoiceActivityDetection`-family pipeline) run over
   `artifacts/stems/vocals.wav` only — no diarization, no ASR/transcription
   (the Whisper decoder itself is never loaded; only the VAD stage of the
   whisperX pipeline runs, which is the plan's own scoping: "whisperX's VAD
   front-end").
2. **Checkpoint**: whisperX's own bundled VAD segmentation model (distinct
   from and unrelated to the gated diarization checkpoint) — 17,719,103
   bytes, sha256 `0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea`,
   downloaded from the `v3.8.6` git tag on the host and `COPY`'d into the
   image (see `Dockerfile`). No download at build time or analysis time.
3. **Frame curve**: the segmentation model's raw per-frame activation
   (~17ms native rate, before hysteresis), resampled onto the shared 50ms
   grid every DSP-based voiceness candidate uses. Reported continuously
   (`voiceness` in [0, 1]), not collapsed to the hard 0/1 call, so a reviewer
   can see *how confidently* voiced a frame was called, not only the binary
   decision.
4. **Phrase spans**: whisperX's own `Binarize` hysteresis binarizer at its
   **library-default** thresholds (`vad_onset=0.500`, `vad_offset=0.363`,
   `min_duration_on=0.1s`, `min_duration_off=0.1s` — the same defaults real
   whisperX transcription runs use, not swept or corpus-fit for this item).
5. **Boundary F1 is scored, not just reported** — the one property that
   distinguishes this candidate from items 5/6: VAD spans carry real
   sub-second onsets/offsets, so `voiceness_common.scorer`'s
   0.25/0.5/1.0s tolerances are a legitimate test here, the same way they are
   for `vocal_voiceness` (item 4). See `score.py`.

**Not run by the queue.** `compute` needs `torch`/`whisperx` (a new research
sandbox image), not the `app` image the queue runner executes in; the
`queue.toml` row uses a non-`app` `image` value so it is honestly recorded
`skipped(needs image ...)`, matching `clap_voiceness`/`svd_tagger`'s own
precedent.

## What was attempted, exactly

Per the task's bounded-effort budget (~25 min total for the heavy Docker/
model parts; stop honestly if exceeded, no retry loop):

1. **Checkpoint pre-fetch (host, bounded ~5 min): SUCCEEDED.** Downloaded
   directly from GitHub's raw content CDN for the `v3.8.6` tag in 2.8s at
   ~6 MB/s (17.7 MB file) and sha256-verified
   (`0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea`). That
   exact file is committed as `vad_pytorch_model.bin` next to this README and
   is what `Dockerfile` `COPY`s in and checksums again at build time.
2. **HF_TOKEN check: no token available.** `echo $HF_TOKEN` empty,
   `~/.cache/huggingface/token` absent. Diarization ruled out before any
   diarization code was written — see "Diarization: not attempted" above.
3. **Image build (bounded, one attempt, ≤15 min): SUCCEEDED.** Applying item
   6's lesson (`COPY` the pre-fetched checkpoint rather than `curl`-ing it
   in-build) avoided that item's network-stall failure mode entirely — all
   `pip install` layers (torch 2.4.1 CPU, whisperX, `pyannote.audio`) and the
   checkpoint `COPY` completed well inside budget.
   `ai-light-song-v2-whisperx-research:dev` built.
4. **`_test_song` compute/export run: SUCCEEDED**, and the full 5-song
   scoring corpus (`_test_song`, `ayuni`, `Hideaway - Kiesza`,
   `Armin - Revolution`, `Titanium - David Guetta ft Sia`) completed within
   budget — see "Results evidence" below.

## Design decisions not fully specified in the plan text

- **Frame grid: 50ms, not whisperX's native ~17ms nor the 1000ms the two
  window-based candidates (items 5/6) use.** Chosen to match `vocal_voiceness`
  (item 4) — the shared grid every DSP-based candidate reports on — since
  VAD's native resolution is already far finer than 50ms and downsampling to
  it loses nothing material while keeping every candidate's frame series
  directly comparable at the scorer's own grid.
- **`Binarize` at library defaults, not whisperX's `merge_chunks`.**
  whisperX's own transcription pipeline additionally regroups `Binarize`'s
  output into ≤30s windows sized for feeding the ASR decoder
  (`whisperx.vads.vad.Vad.merge_chunks`). This experiment skips that step
  entirely — it exists only to batch audio for a Whisper decoder this item
  never loads — and exports `Binarize`'s own hysteresis spans directly as
  `vocal_phrase`, which is the actual VAD phrase boundary the plan is asking
  for, not an ASR-chunking artifact.
- **Confidence on `vocal_phrase` spans**: mean of the raw (un-binarized)
  activation curve over the span — an honest average of the same number the
  frame series already reports, not a new heuristic.
- **No `channel` field.** Single producer, single input (the vocal stem) —
  same shape as `vocal_voiceness`/`clap_voiceness` (items 4/5), unlike
  `svd_tagger`'s stem+mix fusion (item 6). `voiceness_common.schema`'s
  `channel` field is left `None` throughout, per its own documented
  "`None` for a single-producer candidate" convention.

## Future work (not built)

If a Hugging Face token becomes available: a diarization pass, gated
identically to `svd_tagger`'s checkpoint discipline — the gated checkpoint
fetched and checksummed at image **build** time using a token supplied as a
Docker build secret (`--secret`), never at analysis time — scored separately
from the VAD call per the plan ("never folded into the voiceness call"), and
rendered as a distinct sub-lane or color-coded segment in the debugger, never
behind a selector. Given objection 1 above (diarization inherits the VAD's
own false-vocal confusions and adds a speaker label on top, rather than
resolving them), it is not obvious this would improve the false-vocal
question even if the token gate were solved — worth stating rather than
assuming.

## Results evidence

Full table in [`out/score.txt`](out/score.txt). Aggregate across the 5
scoring-corpus songs (0 marked ground-truth spans on every song):

| candidate | avg false_vocal_rate | avg bounds/min |
| --- | --- | --- |
| **whisperx_vad** | **0.3270** | 9.54 |
| `arrangement_state` | 0.5955 | 6.86 |
| `vocal_phrases` | 0.2929 | 46.59 |
| mix-RMS baseline | 0.9219 | 29.02 |

`whisperx_vad` beats `arrangement_state` on this proxy on every song
individually (e.g. `Hideaway - Kiesza` 0.2822 vs 0.8343; `Armin - Revolution`
0.1695 vs 0.6418), but trails `vocal_phrases` in aggregate — `vocal_phrases`
fires far more often (46.6 bounds/min vs 9.5), which on an unmarked proxy
metric inflates its apparent rate advantage rather than proving it's more
correct. Boundary F1 is reported at 0.000 across the board because the
ground-truth span set is empty (0 marked spans, not a detector failure) — the
scorer cannot match a boundary to nothing.

**No ground truth exists yet** — same finding as items 3-6: every
scoring-corpus song has zero `type == "vocal"` hints in this environment.
Every rate above is a firing-rate proxy against an empty marked-span set, not
a validated correctness measure. `is_proxy_no_ground_truth` flags every row.

## Conclusion

**Built, green end-to-end on the full 5-song scoring corpus** — the only one
of the two new-sandbox-image candidates (items 6-7) whose image actually
finished building, by applying item 6's own lesson (pre-fetch + `COPY` instead
of an in-build `curl`). No live token is needed at analysis time (VAD
checkpoint is bundled in `whisperx` itself, plus this item's own
independently-verified copy baked into the image); diarization was
deliberately not attempted given the absent `HF_TOKEN`, documented rather than
discovered at the promotion gate. The proxy table places `whisperx_vad` ahead
of `arrangement_state` on every song and second to `vocal_phrases` in
aggregate — **not a promotion candidate on current evidence**, and the kill
condition is explicitly unevaluable, not passed or failed. Same next step as
every other item-4-7 candidate: mark `type: "vocal"` spans on `ayuni`, then
re-run `score` with no code change — at that point boundary F1 becomes a real
number for this candidate specifically, since its phrase spans carry genuine
sub-second onsets unlike items 5/6's window-based edges.

## Usage

```bash
# build the sandbox image once (see Dockerfile for the checkpoint pin)
docker build -f experiments/whisperx_vad/Dockerfile -t ai-light-song-v2-whisperx-research:dev .

# compute needs torch/whisperx — the whisperx_vad sandbox image
./experiments/whisperx_vad/run_in_container.sh \
    python -m experiments.whisperx_vad.run compute --song <name>

# export/score only read the cache/JSON compute wrote — plain app image
docker compose run --rm app python -m experiments.whisperx_vad.run export --song <name>
docker compose run --rm app python -m experiments.whisperx_vad.run score
```

## `queue.toml`

**Not run automatically by the queue runner** — same precedent as
`clap_voiceness`/`svd_tagger`: `compute` needs `torch`/`whisperx`, only in
the `whisperx-research` sandbox image, and the runner only ever honors
`image = "app"`. The `queue.toml` row uses `image = "whisperx-research"` so
it is recorded `skipped(needs image whisperx-research — run via
run_in_container.sh)` on every queue run rather than silently failing or
being invisible.
