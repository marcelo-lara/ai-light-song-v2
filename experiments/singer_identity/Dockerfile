# Research sandbox for the Singer Identity experiment
# (docs/experiments.md "Singer Identity — open speaker embeddings for 'is
# this a voice, and whose?'").
#
# ECAPA-TDNN speaker embeddings (speechbrain/spkrec-ecapa-voxceleb) run over
# vocal-stem windows gated by whisperx_vad's cached activation.
# `pyannote/speaker-diarization-3.1` is explicitly excluded by the spec (it
# is a gated Hugging Face checkpoint and no HF_TOKEN exists in this
# environment) — ECAPA-TDNN needs no token at all (see model.py's docstring
# and README.md's "Checkpoint" section for the first-hand verification).
#
# --- why a NEW image (not the app image, not a sibling's) -------------------
# `speechbrain` and `scikit-learn` are absent from the `app` image.
# speechbrain 1.1.1 declares only `torch>=2.1.0`/`torchaudio>=2.1.0` on
# paper, but two problems rule out the base image's own pins
# (`torch==2.1.2`/`torchaudio==2.1.2`), both discovered by actually running
# this experiment's smoke test, not by reading metadata:
#   1. The base image ships torch built against CUDA 12.1 alongside
#      torchaudio built against CUDA 11.8 (a latent mismatch invisible until
#      something actually imports `torchaudio`, which nothing in `app` did
#      before this experiment) — `RuntimeError: PyTorch and TorchAudio were
#      compiled with different CUDA versions` at `import speechbrain`.
#   2. speechbrain 1.1.1's `ECAPA_TDNN` attention-pooling layer calls
#      `torch.amp.custom_fwd`/`custom_bwd`, an API introduced in torch 2.4 —
#      torch 2.1.2 has no such attribute, so every embedding call failed
#      with `AttributeError: module 'torch.amp' has no attribute
#      'custom_fwd'` (first smoke-test attempt at 2.1.2, before this pin).
# Resolved by pinning torch/torchaudio 2.4.1 — the same version `svd_tagger`
# (item 6) already validated in this repo — rather than the base image's
# CUDA 2.1.2, sidestepping both problems at once. Originally pulled from the
# CPU wheel index to sidestep every CUDA/driver question too, since this
# item's job was to prove the embedding pipeline runs and clusters, not to
# be fast. Now pulled from the CUDA 12.1 wheel index (`cu121`, verified
# present for 2.4.1) to speed up the corpus-wide run on the host's GTX 1650
# (Turing, sm_75). Same exact version either way — only the wheel variant
# changed. GPU is opt-in via `--device cuda` (see run.py); the default stays
# "cpu". `CUDA_VISIBLE_DEVICES`/`SINGER_IDENTITY_DEVICE` no longer
# hard-disable the GPU at the container level (removed below).
#
# --- the checkpoint: PRE-FETCHED ON THE HOST, COPY'd in, never curled ------
# Applying whisperx_vad's own lesson (item 7's README; svd_tagger's in-build
# curl of a 327 MB file stalled at ~154 KB/s and never completed): every file
# ECAPA-TDNN needs (hyperparams.yaml, embedding_model.ckpt,
# mean_var_norm_emb.ckpt, classifier.ckpt, label_encoder.txt — the last two
# are unused by embedding extraction but declared as `Pretrainer` loadables
# in hyperparams.yaml, so they must be present for the model to load at all)
# was downloaded directly from
# huggingface.co/speechbrain/spkrec-ecapa-voxceleb/resolve/main/ on the HOST
# (unauthenticated — not a gated repo, no HF_TOKEN needed) and sha256-
# verified there (see README.md). None of it is committed to git
# (`.gitignore`, matching whisperx_vad/vad_pytorch_model.bin's precedent) —
# fetch it on the host before building (README.md has the exact commands and
# hashes). `COPY`'d in below, checksummed again at build time. No network
# access for the checkpoint during `docker build`, and none at analysis time
# (model.py always passes the local baked-in directory as both `source` and
# `savedir`, which speechbrain's own `fetch()` resolves without ever
# reaching the network — see model.py's docstring).
FROM ai-light-song-v2:dev

ENV PYTHONPATH=/app \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_OFFLINE=1

RUN pip install --no-cache-dir "speechbrain==1.1.1" "scikit-learn>=1.3,<2"

# torch/torchaudio 2.4.1 — see "why a NEW image" above for both reasons this
# must not be the base image's CUDA 2.1.2. cu121 wheel variant (see header).
RUN pip install --no-cache-dir --force-reinstall \
      --index-url https://download.pytorch.org/whl/cu121 \
      "torch==2.4.1" "torchaudio==2.4.1"

# --- pinned checkpoint, pre-fetched on the HOST, COPY'd (never curled) -----
# NOT under /app: run_in_container.sh bind-mounts the host repo over /app
# (same as every sibling sandbox), which would shadow anything baked in
# there at image-build time.
COPY experiments/singer_identity/ecapa_checkpoint /models/singer_identity/ecapa_checkpoint
ARG SI_HYPERPARAMS_SHA256="6f78854fa04ba59e761437b76a2575d3aba5e5016de3e9b69f0c9a5077fb1a41"
ARG SI_EMBEDDING_MODEL_SHA256="0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2"
ARG SI_MEAN_VAR_NORM_EMB_SHA256="cd70225b05b37be64fc5a95e24395d804231d43f74b2e1e5a513db7b69b34c33"
ARG SI_CLASSIFIER_SHA256="fd9e3634fe68bd0a427c95e354c0c677374f62b3f434e45b78599950d860d535"
ARG SI_LABEL_ENCODER_SHA256="e13c3a167bb4112685670ee896d20e2b565af16b3a4ceeaa8689fa4d22adb8b9"
RUN cd /models/singer_identity/ecapa_checkpoint && \
    echo "${SI_HYPERPARAMS_SHA256}  hyperparams.yaml" | sha256sum -c - && \
    echo "${SI_EMBEDDING_MODEL_SHA256}  embedding_model.ckpt" | sha256sum -c - && \
    echo "${SI_MEAN_VAR_NORM_EMB_SHA256}  mean_var_norm_emb.ckpt" | sha256sum -c - && \
    echo "${SI_CLASSIFIER_SHA256}  classifier.ckpt" | sha256sum -c - && \
    echo "${SI_LABEL_ENCODER_SHA256}  label_encoder.txt" | sha256sum -c -
