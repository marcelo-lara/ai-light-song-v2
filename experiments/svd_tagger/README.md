# SVD Tagger — PANNs `Singing` head, stem vs mix

*(PANNs Cnn14 AudioSet-527 tagger — new sandbox image, new model pin)*

**Does a pretrained tagger's `Singing` class beat a hand-built discriminator
at the same job?** The strongest-prior, highest-cost candidate in the
false-vocal family (items 4-7): PANNs was explicitly trained to distinguish
"Singing" from AudioSet's other 526 classes, so if any candidate could show a
hand-built cue set unnecessary, this is it.

## Status

**BLOCKED — image build attempted once, timed out mid-checkpoint-download.**
v3.5 item 6. All Python (`model.py`, `export.py`, `run.py`, `score.py`) and
the `Dockerfile` / `run_in_container.sh` are written and follow the
`clap_voiceness` (item 5) shape exactly. `pip install` of torch 2.4.1 CPU +
`panns-inference==0.1.1` completed successfully inside the build. The build
was killed by its own 15-minute bounded timeout while downloading the pinned
327 MB PANNs checkpoint from Zenodo — see "What was actually attempted"
below for the exact point of failure. **No `compute`/`export`/`score` run
has happened** — the image was never produced.

## Why? What for?

`arrangement_state` reports `vocals` present 40.8% of `ayuni` — the
false-vocal question items 3-7 chase from different angles. Items 4/5 use
hand-built pitch/spectral cues and a CLAP contrastive pair; this item asks
whether a general-purpose audio tagger's own `Singing` class, trained
directly on the discrimination, does better — on both the vocal stem (should
be near-ceiling if the stem separation is clean) and the mix (the actual
false-vocal confusion: pitched instruments vs. a real vocal, un-stemmed).

## Method

1. **Model**: PANNs (Kong et al., <https://arxiv.org/abs/1912.10211>) Cnn14,
   checkpoint `Cnn14_mAP=0.431.pth` — D6.1 in the implementation plan
   resolved PANNs over BEATs (smaller, stable checkpoint, narrower dependency
   footprint).
2. **Class**: AudioSet-527's `"Singing"` class, index 27 (0-indexed; verified
   directly against `class_labels_indices.csv` from
   `qiuqiangkong/audioset_tagging_cnn` this session — see `model.py`
   docstring for the exact CSV hash).
3. **Grid**: no frame-level PANNs checkpoint is used (that needs a second
   pin, `Cnn14_DecisionLevelMax` — not built, out of scope for this item).
   Instead: clip-level `AudioTagging.inference()` over a 5s window / 1s hop,
   same sliding-window shape as `experiments/clap/model.py`. `interval_ms:
   1000` in the exported proposal, not upsampled.
4. **Both channels, one file**: the tagger runs once over
   `artifacts/stems/vocals.wav` and once over `data/songs/<song>.mp3` (**the
   mix** — there is no `stems/mix.wav`; `SongPaths` writes only
   vocals/bass/drums/harmonic stems, so "the mix" is the original,
   un-stemmed song audio, matching `experiments/clap/paths.py::audio_path`'s
   own convention). Every exported `VoicenessFrame`/`VocalPhrase` carries
   `channel: "stem" | "mix"` — see `export.py` docstring — genuinely
   different producers of the same call, never silently picked.
5. **Confidence**: `|voiceness - 0.5| * 2`, the same decision-margin
   heuristic items 4/5 use.

## Cost — the kill condition's other half

This is the only item 4-7 candidate needing a **new sandbox image** (torch
2.4 CPU + `panns_inference`, ~2-3 GB image) **and a new model pin** (a
327 MB checkpoint, sha256-verified at image build time, never at analysis
time — see `Dockerfile`). The kill condition
(`docs/implementation-plan-v3.5.md`, D6.1 area) is explicitly: does not beat
item 4 on `ayuni`'s false-vocal rate, **given this cost** — a technically-equal
score is not a win here, because items 4/5 pay no image/pin cost at all.

## What was actually attempted

Per the task's resource guidance (bounded effort — image build attempted
once, ≤ 10-15 min, no retry loop):

1. The pinned checkpoint (`Cnn14_mAP=0.431.pth`, Zenodo record 3987831,
   `Content-Length: 327428481` bytes) was downloaded directly from the host
   shell this session (2m1s, ~2.7 MB/s effective) and sha256-verified —
   `0dc499e40e9761ef5ea061ffc77697697f277f6a960894903df3ada000e34b31` — and
   that exact, first-hand-verified hash is what `Dockerfile` pins and checks
   at build time. `panns-inference==0.1.1` was confirmed to exist on PyPI.
   `class_labels_indices.csv` was fetched and checked to confirm `"Singing"`
   is AudioSet-527 class index 27 (0-indexed).

2. **`docker build -f experiments/svd_tagger/Dockerfile -t
   ai-light-song-v2-svd-research:dev .` was run once**, wrapped in `timeout
   900` (15 min), the outer bound the task allowed. Result: **killed by its
   own timeout at 14m59s, exit code 143. Not retried**, per the task's
   explicit "stop immediately, do not retry" instruction.

   **Exact point of failure** (from `docker buildx history logs`, the
   buildkit record of that build): every `pip install` step (torch 2.4.1 CPU,
   `panns-inference`, `librosa`, `soundfile`, the forced torch/numpy
   reinstalls) **completed successfully** — steps `#1`-`#6` all finished.
   The build reached step `#7`, the checkpoint `curl`, and stalled there:

   ```
   #7 [4/4] RUN mkdir -p /app/models/panns && curl -fL --retry 3 -o "/app/models/panns/Cnn14_mAP=0.431.pth" "https://zenodo.org/records/3987831/files/Cnn14_mAP=0.431.pth" && echo "<sha256>  ..." | sha256sum -c -
   #7 0.187   % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
   ...
   #7 ...  0  312M    0  376k    0     0   154k      0  0:34:2[7] ...
   #7 CANCELED
   ```

   `curl` inside the build container was transferring at **~154 KB/s**
   (ETA ~34 minutes for the 312 MiB file) — roughly 17× slower than the same
   URL's ~2.7 MB/s from the host shell moments earlier. Only ~376 KB of
   327,428,481 bytes had downloaded when the 15-minute budget expired and
   the step was canceled. This looks like a build-container network-path
   constraint (proxy/rate-limit specific to the Docker build network, not a
   dead URL or a bad pin — the same URL was fast from the host) rather than
   anything wrong with the Dockerfile itself.

3. **Step 3 of the task (`_test_song` compute/export run) was never
   reached** — there is no image to run it in.

**Design decision for the operator to record (D-item):** either (a) bake the
checkpoint into the image via a `COPY` of a pre-fetched, host-verified file
instead of an in-build `curl` (trades "no network dependency at build
either" for "a 312 MB file must be staged next to the Dockerfile, likely
outside git"), or (b) retry the build with a longer bound / on a host with a
faster build-network path, since the pip layers already prove the rest of
the Dockerfile is correct. Not decided here — this item's job was to prove
or disprove the pipeline within budget, and it disproved it within the
budget given, honestly, not by faking a number.

## Results evidence

**None yet.** No `compute` run has produced cache files under
`experiments/svd_tagger/cache/`, so there is no results table — an honest
`unknown`, not a fabricated number (CLAUDE.md: no silent fallbacks).

## Usage

```bash
# build the sandbox image once (see Dockerfile for the checkpoint pin)
docker build -f experiments/svd_tagger/Dockerfile -t ai-light-song-v2-svd-research:dev .

# compute needs torch/panns_inference — the svd_tagger sandbox image
./experiments/svd_tagger/run_in_container.sh \
    python -m experiments.svd_tagger.run compute --song <name>

# export/score only read the cache/JSON compute wrote — plain app image
docker compose run --rm app python -m experiments.svd_tagger.run export --song <name>
docker compose run --rm app python -m experiments.svd_tagger.run score
```

## `queue.toml`

**Not run automatically by the queue runner** — same precedent as
`clap_voiceness`: `compute` needs `torch`/`panns_inference`, only in the
`svd-research` sandbox image, and the runner only ever honors `image =
"app"`. The `queue.toml` row uses `image = "svd-research"` so it is recorded
`skipped(needs image svd-research — run via run_in_container.sh)` on every
queue run rather than silently failing or being invisible. Both steps must
be run manually via `run_in_container.sh` / `docker compose run app`.

## Conclusion

Scaffold complete and matches the `clap_voiceness` (item 5) shape: `model.py`
/ `export.py` / `score.py` / `run.py`, the shared `voiceness_common` schema
(extended with an optional per-row `channel` field for this item's two-
producer case — see `voiceness_common/schema.py`), the shared scorer against
all three incumbents for both channels, and the debugger lane
(`6. SVD Tagger`, both channels as two curves, no toggle). The Dockerfile's
`pip install` layers are proven correct (they completed in the one build
attempt); the checkpoint-download layer is not — it stalled at ~154 KB/s
inside the build network and was canceled by the 15-minute budget with
376 KB of 312 MiB fetched. **No measured result exists and none is
invented.** This item's kill condition is unevaluated, not passed or
failed, and — per the task's explicit "stop, do not retry" instruction —
was not retried. The next step is either re-attempting the build with a
longer bound / on a faster build-network path, or switching the checkpoint
to a `COPY`-in of a pre-fetched, host-verified file (see the D-item above),
followed by one `compute`/`export`/`score` run on `_test_song`.
