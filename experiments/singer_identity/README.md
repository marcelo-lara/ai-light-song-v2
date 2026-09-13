# Singer Identity — ECAPA-TDNN speaker embeddings over the vocal stem

*(new sandbox image, new checkpoint pin — reuses `whisperx_vad`'s cached VAD, no diarization)*

**Is this a voice, and whose?** Two outputs from one pass, per
`docs/experiments.md` "Singer Identity": **`voice_similarity`** (per-window
cosine similarity to the song's nearest voice cluster centroid — should
reject a loud non-vocal false positive that `whisperx_vad`'s own VAD gate
lets through) and **`singer_change`** (cluster-switch points between
consecutive embedded windows — a duet handoff or lead-to-stacked-chorus
change, a real moving-head cue nothing else in the pipeline produces).

## Status

**BUILT, not yet scored.** All Python (`paths.py`, `model.py`, `export.py`,
`score.py`, `run.py`), `Dockerfile`, `run_in_container.sh`, the
`docker-compose.yml` service (`singer-identity`) and the `queue.toml` row are
written, following `whisperx_vad`'s shape exactly and plugging into the
shared `voiceness_common.schema`/`scorer`/`incumbents`. Per the operator's
rule, running the experiment on the scoring corpus and filling in the
results table is a separate, later step — **not done here.** Only a
crash-only smoke test on `_test_song` (`compute` then `export`) has been run.

## Method

1. **Voiced candidates**: `whisperx_vad`'s cached per-frame activation
   (`experiments/whisperx_vad/cache/<song>.npz`, read-only, never
   recomputed) at `>= 0.2` mean over each window — reusing its own VAD call
   rather than re-running VAD.
2. **Windows**: 1.5s, 0.25s hop, over `artifacts/stems/vocals.wav` resampled
   to 16kHz mono.
3. **Embeddings**: ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`), every
   window that clears the VAD gate above — including one that clears it
   falsely (a loud instrumental), which is the point: its embedding should
   sit far from any voice centroid even though the VAD gate itself fired.
4. **Clustering**: agglomerative, cosine affinity, average linkage, over the
   embedded windows; k in {2, 3, 4} chosen by `silhouette_score`, **then
   collapsed to k=1 by an explicit test** (fixed 2026-09-13 — see "k=1
   collapse test" below). Silhouette alone can never pick k=1 (undefined for
   a single cluster), so the original code seeded `best_k=1, best_score=0.0`
   and compared with `>` — a real silhouette score is essentially always
   > 0, so k=1 could never win. Corpus-wide k distribution under that bug:
   {2: 19, 3: 3, 4: 1} — k=1 selected zero times, including on solo-vocalist
   songs (e.g. `Titanium` emitted 39 `singer_change` points at 10.1/min from
   one singer flapping between two phantom clusters).
5. **`voice_similarity`**: each embedded window's cosine similarity to its
   nearest cluster centroid, written into the shared `voiceness` field so
   `voiceness_common.scorer` scores it with no new scoring code. A window
   below the VAD gate is not embedded and is reported as `0.0`/`confidence:
   null` by construction (the gate itself is the "no voice" claim, inherited
   from `whisperx_vad`, not a guessed similarity). A window that clears the
   gate but whose embedding step itself fails is **omitted from the exported
   series entirely** (the schema's `voiceness` field is not nullable) and
   logged in `generated_from_extra["embedding_failures"]` — no guessed value
   ever stands in.
6. **Emitted on the shared 50ms grid, by nearest-window hold** (decided
   2026-09-12, `docs/experiments.md` "Singer Identity"): the native unit of
   measurement is the 1.5s window/0.25s hop itself — there is nothing finer
   to resample from — but `export.py` writes one row per 50ms frame, each
   taking the value of the native window whose centre is nearest it (a hold,
   not `whisperx_vad`'s `np.interp` — the value is constant across its whole
   native window, so interpolation would invent a slope that isn't there).
   Frame times are read straight from `whisperx_vad`'s own cached grid, so
   the two proposals are frame-identical, not just similarly spaced — the
   point of the change, since it is what lets a per-frame AND against
   `whisperx_vad`/`vocal_voiceness`/`clap_voiceness` work at all.
   `generated_from` carries both the true native resolution
   (`native_window_s`/`native_hop_s`) and the emission grid
   (`emission_grid_s`), so no reader mistakes 50ms of precision for something
   this candidate actually measured. A 50ms frame outside every native
   window's `[start, end]` span (in practice: past the last window's tail,
   where the native windows stop at the vocal stem's own duration rather
   than landing exactly on the shared grid's last step) is held at
   `0.0`/`confidence: null` with the reason recorded in
   `generated_from_extra["grid_frames_uncovered_reason"]` — the hold never
   invents coverage outside the embedded region. On `_test_song`: 227 native
   windows became 1163 grid frames, 2 of them uncovered at the tail.
7. **`singer_change`**: fires between consecutive embedded windows whose
   nearest-centroid cluster differs; `confidence` is the lower of the two
   windows' own nearest-centroid similarities. Rides along as a top-level key
   in the exported JSON (not folded into `generated_from` metadata, since it
   is a real output, not provenance) — see `export.py`.

## k=1 collapse test (2026-09-13)

After the silhouette pick above (still only ever over k in {2, 3, 4}), two
named constants in `model.py` decide whether to collapse that pick to k=1:

- **`SILHOUETTE_FLOOR = 0.1`** — the winning silhouette must clear this or
  the split isn't supported by the clustering geometry at all; k=1 stands
  unconditionally, no centroid comparison needed.
- **`MERGE_SIMILARITY = 0.5`** — otherwise, iteratively merge the closest
  centroid pair (cosine similarity, recomputed after each merge) while their
  similarity exceeds this; the surviving cluster count is the final k. Above
  0.5 cosine, two ECAPA-TDNN/voxceleb centroids are read as the same voice.

Both are starting points for ECAPA-TDNN/voxceleb cosine space, **not
hand-tuned against this corpus** — `run.py calibrate` (below) is what
justifies keeping or moving them, against `singer_ground_truth.json`'s
declared `lead_voices`.

Verified on synthetic embeddings (not the real corpus, since the corpus-wide
recompute is a separate, later step): one noisy cluster around a single
center collapses to k=1 (silhouette 0.078, centroid similarity ~1.0); two
well-separated centers stay at k=2 (silhouette 0.685, centroid similarity
-0.013). On `_test_song` (not in `singer_ground_truth.json`) the four
silhouette-picked clusters have a max pairwise similarity of 0.444 — below
`MERGE_SIMILARITY` — so k stays 4; this only shows the test doesn't
force a collapse where centroids are already genuinely distinct, not
anything about `_test_song`'s real singer count.

## Cached arrays (`experiments/singer_identity/cache/<song>.npz`)

Beyond `cluster_of_window`/`similarity`/`k` (unchanged), the cache now also
holds the raw material the k decision was made from, so a future
re-clustering (e.g. re-running the collapse test with different constants)
needs no GPU pass over the audio:

- `embeddings` — the `(n_embedded, 192)` float32 matrix actually clustered.
- `embedded_window_index` — the window indices those rows correspond to.
- `centroid_similarity` — the final `(k, k)` pairwise cosine similarity
  matrix of the winning centroids.
- `silhouette` — the winning k>=2 silhouette score, or `nan` when no k>=2
  was even evaluable (fewer than 3 embedded windows).

`export.py` surfaces `silhouette` and the max off-diagonal
`centroid_similarity` (both `null` when not applicable, e.g. k=1) into
`generated_from_extra` alongside `k`, so the k decision is auditable from
the published proposal alone.

## Singer-count calibration (`run.py calibrate`)

```bash
docker compose run --rm app python -m experiments.singer_identity.run calibrate
```

Reads every song's cache (never recomputes; fails loud — not skips — if a
declared song in `singer_ground_truth.json` has no cache, or an older cache
that predates this fix). Reports, per song: declared `lead_voices` vs
predicted `k`, the winning silhouette, max centroid similarity, and
`singer_change` count/rate. Accuracy is computed only over the 9
`extra_speech: false` songs; the 2 `extra_speech: true` songs are listed
separately (k >= declared is acceptable there, k < declared is not) and
never folded into the accuracy. Songs with a cache but no ground-truth entry
print in a separate "unscoreable" block, predicted k only — `calibrate`
never invents a `lead_voices` value for them. Output also written to
`out/singer_count_calibration.txt`.

**Not yet run corpus-wide** — the caches most songs currently have predate
this fix (built before 2026-09-13) and `calibrate` fails loud on them by
design; the operator's corpus recompute is a separate, later step.

## Checkpoint

**Not gated.** `speechbrain/spkrec-ecapa-voxceleb` on Hugging Face —
unauthenticated `curl` against
`huggingface.co/speechbrain/spkrec-ecapa-voxceleb/resolve/main/...` succeeds
with no `HF_TOKEN` set (verified first-hand this session). All five files
the model's own `hyperparams.yaml` `Pretrainer` declares as loadables were
fetched on the **host**, sha256-verified there, and are `COPY`'d into the
image (never curled inside `docker build`, applying `whisperx_vad`'s own
lesson — `svd_tagger`'s in-build curl of a 327 MB file stalled and never
finished). Commit `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286` of the repo:

| file | sha256 | bytes |
| --- | --- | --- |
| `hyperparams.yaml` | `6f78854fa04ba59e761437b76a2575d3aba5e5016de3e9b69f0c9a5077fb1a41` | 1,919 |
| `embedding_model.ckpt` | `0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2` | 83,316,686 |
| `mean_var_norm_emb.ckpt` | `cd70225b05b37be64fc5a95e24395d804231d43f74b2e1e5a513db7b69b34c33` | 1,921 |
| `classifier.ckpt` | `fd9e3634fe68bd0a427c95e354c0c677374f62b3f434e45b78599950d860d535` | 5,534,328 |
| `label_encoder.txt` | `e13c3a167bb4112685670ee896d20e2b565af16b3a4ceeaa8689fa4d22adb8b9` | 128,619 |

`classifier.ckpt`/`label_encoder.txt` are unused by embedding extraction but
must be present for `EncoderClassifier.from_hparams` to load at all (they are
declared `Pretrainer` loadables in `hyperparams.yaml`).

None of it is committed to git (`.gitignore`, matching
`experiments/whisperx_vad/vad_pytorch_model.bin`'s precedent). Re-fetch
before building:

```bash
mkdir -p experiments/singer_identity/ecapa_checkpoint && cd experiments/singer_identity/ecapa_checkpoint
BASE=https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb/resolve/main
for f in hyperparams.yaml embedding_model.ckpt mean_var_norm_emb.ckpt classifier.ckpt label_encoder.txt; do
  curl -fL -o "$f" "$BASE/$f"
done
sha256sum *   # compare against the table above
```

**No download of any kind happens at image build time or at analysis time.**
`model.py` passes the baked-in local directory as `source`/`savedir` to
`EncoderClassifier.from_hparams`, **and** overrides `hyperparams.yaml`'s own
baked-in `pretrained_path: speechbrain/spkrec-ecapa-voxceleb` (an HF repo id,
since the yaml is fetched from the Hub verbatim) to that same local
directory via `overrides={"pretrained_path": ...}`. Both are required: the
first smoke-test run without the override reached the network anyway and
failed loud under `HF_HUB_OFFLINE=1` (`Pretrainer.collect_files` resolves
each loadable's path from `pretrained_path` directly, ignoring `source`
whenever `hyperparams.yaml` already declares an explicit path — verified
against speechbrain 1.1.1's own `parameter_transfer.py` this session, and
against the actual failure in this environment before the fix). See
`model.py`'s `_load_encoder` docstring for the exact mechanism.

## Determinism — the automatic kill clause

**A candidate that needs a live token at analysis time cannot be promoted
regardless of its score.** ECAPA-TDNN does not trigger this clause (see
"Checkpoint" above). `pyannote/speaker-diarization-3.1` **would** trigger it
and is why the spec excludes it outright — it needs an HF token, none exists
in this environment, and it was never attempted here (unlike `whisperx_vad`,
this item does not even build a VAD-only fallback around it, since ECAPA is
the whole method).

## Kill condition

Per the spec: killed if `voice_similarity` neither beats `whisperx_vad`'s
`false_vocal_rate` on `Cinderella - Ella Lee` nor matches it on `ayuni`.
`singer_change` is reported as a **negative** if it splits one singer's own
registers more often than it finds a real singer change (expected — these
models are speech-trained and on singing they cluster by timbre *and* pitch
register). **Neither has been evaluated yet** — see "Results evidence".

## Design decisions not fully specified in the plan text

- **`score.py` scores the exact 50ms series `export.py` publishes — one
  definition, not two.** `export.build_frames()` is the sole implementation
  of the emitted series; `score.py`'s `_candidate_frames_phrases` reads the
  already-written `reference/proposals/singer_identity.json` when it exists
  (literally what a consumer would read) and otherwise calls
  `export.build_frames()` directly if `export` hasn't run yet for the song —
  it never re-derives the native-hop series itself. Scoring at 0.25s while
  publishing at 50ms would defeat the reason the grid decision exists: the
  numbers this candidate is judged by (matching/beating `whisperx_vad`'s
  frame_acc/false_vocal_rate) have to describe the same object the debugger
  and any per-frame AND actually read.
- **`vocal_phrase` is left empty.** This candidate does not derive phrase
  segmentation (that is `whisperx_vad`'s job, reused via the VAD gate) — only
  `voice_similarity` and `singer_change` are its actual output.
- **Below-gate frames get `0.0`/`null`, not an omitted frame.** Chosen so the
  exported series stays a usable continuous curve over the whole song (like
  every sibling candidate's `voiceness`), while a genuine embedding failure
  (rare, e.g. a too-short tail segment) is omitted rather than defaulted —
  the two cases are different in kind (a design decision vs. a failure) and
  are documented separately in `model.py`.
- **CPU-only torch/torchaudio 2.4.1, not the base image's CUDA 2.1.2** —
  discovered by actually running the smoke test, not by reading metadata.
  Two separate failures at 2.1.2: (1) the base image's torch (CUDA 12.1)
  and torchaudio (CUDA 11.8) are mutually incompatible, surfacing only once
  something imports `torchaudio` (speechbrain does, unconditionally); (2)
  speechbrain 1.1.1's `ECAPA_TDNN` calls `torch.amp.custom_fwd`, a torch 2.4+
  API absent from 2.1.2. 2.4.1 (the version `svd_tagger` already validated
  CPU-only in this repo) resolves both. **Update (2026-09-13):** the image
  now installs this same 2.4.1 pin from the `cu121` CUDA wheel index instead
  of the CPU index, and `CUDA_VISIBLE_DEVICES`/`SINGER_IDENTITY_DEVICE` no
  longer force CPU at the container level — GPU is opt-in via `--device
  cuda` (default stays `cpu`).

## Usage

```bash
docker compose build singer-identity   # builds the sandbox image

# compute needs speechbrain/scikit-learn — the singer-identity sandbox
docker compose run --rm --no-deps -T singer-identity \
    python -m experiments.singer_identity.run compute --song <name>

# export/score only read the cache/JSON compute wrote — plain app image
docker compose run --rm app python -m experiments.singer_identity.run export --song <name>
docker compose run --rm app python -m experiments.singer_identity.run score
```

`compute` requires `experiments/whisperx_vad`'s own cache to already exist
for the song (`experiments/whisperx_vad/cache/<song>.npz`) — it is read, not
recomputed.

## `queue.toml`

**Not run automatically by the queue runner** — same precedent as
`clap_voiceness`/`svd_tagger`/`whisperx_vad`: `compute` needs
`speechbrain`/`scikit-learn`, only in the `singer-identity` sandbox image,
and the runner only ever honors `image = "app"`. The row uses
`image = "singer-identity"` so it is recorded
`skipped(needs image singer-identity — run via docker compose run --no-deps
singer-identity)` on every queue run.

## Results evidence

**Not yet run.** Per the operator's rule, running the experiment on the
scoring corpus and scoring it is a separate later step. This smoke test only
confirmed `compute`/`export` run clean on `_test_song` (see "Smoke test"
below) — `_test_song` has no `type: "vocal"` hints and is absent from
`vocal_ground_truth.json`, so `score` fails loud on it, correctly, and was
not run.

| candidate | avg frame_acc | avg false_vocal_rate | avg bounds/min | singer_change @ Armin handoff |
| --- | --- | --- | --- | --- |
| `singer_identity` | — | — | — | — |
| `whisperx_vad` | — | — | — | n/a |
| `arrangement_state` | — | — | — | n/a |
| `vocal_phrases` | — | — | — | n/a |
| mix-RMS baseline | — | — | — | n/a |

## Smoke test

```bash
docker compose run --rm --no-deps -T singer-identity python -m experiments.singer_identity.run compute --song _test_song \
  && docker compose run --rm app python -m experiments.singer_identity.run export --song _test_song
```

Crash-only, on `_test_song` only — no other song, no `score`. Ran clean
before and after the 2026-09-13 k=1 fix; `_test_song`'s own k was 4 both
times (its four silhouette-picked centroids are genuinely separated — max
pairwise similarity 0.444, below `MERGE_SIMILARITY` — so this song was never
a case the fix should change). The fix's correctness was instead verified on
synthetic embeddings (see "k=1 collapse test" above) and structurally via
`run.py calibrate` failing loud on the pre-fix corpus caches, exactly as
designed.

## Decisions made after the first build (2026-09-12)

Both open questions the first build left in "Future work" are now resolved,
per `docs/experiments.md` "Singer Identity" — "Two decisions the first build
left open":

- **`voice_similarity`'s grid**: resample to the shared 50ms grid (method
  step 6 above) — done, not left coarse, since the whole point of the shared
  grid is a per-frame AND across candidates.
- **`singer_change` scoring**: stays a **manual ear check** permanently, not
  a scorer. The corpus has exactly one marked singer change (`Armin -
  Revolution`, male → female at ~81.6s) — a metric over one event measures
  nothing. Revisit only if more handoffs get marked.
