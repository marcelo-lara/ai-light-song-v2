# SVD Tagger — PANNs `Singing` head, stem vs mix

*(PANNs Cnn14 AudioSet-527 tagger — new sandbox image, new model pin)*

**Does a pretrained tagger's `Singing` class beat a hand-built discriminator
at the same job?** The strongest-prior, highest-cost candidate in the
false-vocal family (items 4-7): PANNs was explicitly trained to distinguish
"Singing" from AudioSet's other 526 classes, so if any candidate could show a
hand-built cue set unnecessary, this is it.

## Status

**OPEN — built, run over all 23 songs, scored on the 5 declared songs.** v3.5
item 6. Neither promoted nor killed — that is the operator's call; see
"Results evidence".

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

## Checkpoint pin

`Cnn14_mAP=0.431.pth` (Zenodo record 3987831, 327,428,481 bytes, sha256
`0dc499e40e9761ef5ea061ffc77697697f277f6a960894903df3ada000e34b31`), fetched by
an in-build `curl` and sha256-checked in `Dockerfile`. The first build attempt
was killed at its 15-minute bound (~154 KB/s inside the build network vs
~2.7 MB/s from the host); a later build completed. If it stalls again, pre-fetch
on the host and `COPY` it in, as `whisperx_vad` does.

## Results evidence

Full table in [`out/score.txt`](out/score.txt). v3.5 corpus rebuild (2026-09-13),
three-class scorer, the 5 declared songs. Only `ayuni` and `Cinderella` declare
negatives, so only they separate detectors. frame_acc / false_vocal_rate /
residual firing:

| candidate | `ayuni` | `Cinderella` |
| --- | --- | --- |
| `svd_tagger_stem` (raw) | 0.7538 / 0.0000 / 0.00 | 0.3083 / 0.0000 / — |
| `svd_tagger_mix` (raw) | 0.7538 / 0.0000 / 0.00 | 0.3042 / 0.0000 / — |
| `svd_tagger_stem_p98` | 0.8077 / 0.0154 / 0.23 | 0.4417 / 0.0083 / — |
| `svd_tagger_mix_p98` | 0.8538 / 0.0077 / 0.07 | 0.5125 / 0.0000 / — |
| `whisperx_vad` (promoted) | 0.9881 / 0.0056 / 0.24 | 0.8614 / 0.0290 / — |
| `arrangement_state` | 0.9042 / 0.0891 / 0.82 | 0.9342 / 0.0035 / — |

`Cinderella` rescored 2026-09-13 against v3.5 item 12's repaired class map (22
positive / 5 negative spans, was 4/4); per-channel AUC below supersedes the
earlier single unlabelled figure.

- **Raw:** discriminates (AUC pos-vs-neg `ayuni` stem 0.915 / mix 0.872,
  `Cinderella` stem 0.931 / mix 0.959) but peaks at 0.14-0.50, so the shared 0.5
  threshold never fires; its frame_acc is just the negative-class fraction.
- **`_p98`** (`model.rescale_per_song`, divide by the song's own p98 — declared,
  not swept): fires, rarely wrongly, but still misses most vocal frames
  (0.9-2.2 bounds/min). Does not reach either incumbent.

## Usage

**Update (2026-09-13):** the image now installs torch/torchaudio 2.4.1 from
the `cu121` CUDA wheel index rather than the CPU index, and
`CUDA_VISIBLE_DEVICES`/`SVD_TAGGER_DEVICE` no longer force CPU at the
container level. GPU is opt-in via `--device cuda` (default stays `cpu`).

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

**No promotion case; keep/kill is the operator's call.** A correctly-ordered
signal whose calibration is off, and a per-song rescale does not fix that
enough: best 0.8538 / 0.5125 against whisperX's 0.9881 / 0.8614. Its one
distinctive number is `mix_p98`'s 0.07 residual firing on `ayuni`. Cost: its own
image plus a 327 MB pin.
