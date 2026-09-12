# Research sandbox for the WhisperX VAD experiment (v3.5 item 7 —
# implementation-plan-v3.5.md "whisperx_vad").
#
# whisperX (Max Bain et al., https://github.com/m-bain/whisperX) pinned at
# 3.8.6 — its VAD front-end only, never its ASR/alignment/diarization path.
#
# --- why a NEW image (not the app image, not svd_tagger's) -----------------
# `transformers` is absent from the `app` image (D6/D7's own finding, repeated
# here). whisperX 3.8.6 additionally pins `torch~=2.8.0` / `torchaudio~=2.8.0`
# — verified directly against its `pyproject.toml` this session — which is
# far newer than the app image's `torch==2.1.2` / CUDA 11.8 base
# (`requirements.txt`) and also newer than svd_tagger's own pinned CPU
# `torch==2.4.1`, so neither existing image can host it without breaking
# something else. Same resolution as items 5/6: CPU-only torch sidesteps any
# CUDA/driver compatibility question entirely — this item's job is to prove
# the pipeline runs and produce a score, not to be fast.
#
# --- the checkpoint: PRE-FETCHED ON THE HOST, COPY'd in, never curled ------
# Item 6 (svd_tagger)'s Dockerfile curled its 327 MB PANNs checkpoint FROM
# INSIDE the build and stalled at ~154 KB/s, never completing within a
# 15-minute budget (see experiments/svd_tagger/README.md). This Dockerfile
# applies that lesson directly: whisperX's VAD segmentation checkpoint
# (17,719,103 bytes, NOT the gated pyannote/speaker-diarization-3.1 model —
# see model.py's docstring) was downloaded from the `v3.8.6` git tag on the
# HOST shell this session (2.8s, ~6 MB/s) and sha256-verified there
# (0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea). It is
# NOT committed to git (`.gitignore`: no binary model checkpoints, matching
# the repo-wide `models/` convention) — fetch it on the host before building:
#
#   curl -sL -o experiments/whisperx_vad/vad_pytorch_model.bin \
#     https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/assets/pytorch_model.bin
#   sha256sum experiments/whisperx_vad/vad_pytorch_model.bin
#   # expect: 0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea
#
# `COPY`'d in below once present — no network access during `docker build`
# for the checkpoint either way, and none at analysis time (model.py loads it
# from this fixed baked-in path, never whisperX's own bundled copy or any
# Hugging Face URL).
FROM ai-light-song-v2:dev

ENV PYTHONPATH=/app \
    TOKENIZERS_PARALLELISM=false \
    WHISPERX_VAD_DEVICE=cpu \
    CUDA_VISIBLE_DEVICES="" \
    HF_HUB_OFFLINE=1

# CPU torch pinned to whisperX 3.8.6's own requirement (torch~=2.8.0,
# torchaudio~=2.8.0), overriding the base image's CUDA 11.8 / torch 2.1.2.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
      "torch==2.8.0" "torchaudio==2.8.0"

# whisperX itself. Pulls pyannote-audio>=4.0.0 (which pulls
# pytorch-lightning + torchmetrics + torchvision transitively — none of
# whisperx's own direct deps, but torchmetrics imports torchvision
# unconditionally at import time), transformers, huggingface-hub,
# faster-whisper/ctranslate2 (ASR path — unused by this item, but whisperX is
# one package and the VAD-only subset is not published separately), pandas,
# nltk. `HF_HUB_OFFLINE=1` (set above) makes any accidental Hugging Face Hub
# call at runtime fail loudly instead of silently reaching the network —
# this item touches the Hub only through a local file path, never a repo id.
#
# `pip install whisperx` alone resolves torch/torchaudio/torchvision off
# PyPI's default index (CUDA wheels), which is what the base image already
# discourages (D5/D6's own reasoning) and is large. The first attempt at
# this Dockerfile force-reinstalled only torch/torchaudio from the CPU index
# afterward and left torchvision at its CUDA-resolved build — that ABI
# mismatch crashes on `import torchvision` ("operator torchvision::nms does
# not exist"), surfaced when the sandbox image's first compute run failed.
# Fixed by force-reinstalling torchvision from the same CPU index alongside
# torch/torchaudio, pinned to the version whisperx's own pyproject.toml
# requires (torchvision~=0.23.0, verified against the v3.8.6 tag).
RUN pip install --no-cache-dir "whisperx==3.8.6" \
 && pip install --no-cache-dir --force-reinstall \
      --index-url https://download.pytorch.org/whl/cpu \
      "torch==2.8.0" "torchaudio==2.8.0" "torchvision==0.23.0"

# --- pinned checkpoint, pre-fetched on the HOST, COPY'd (never curled) -----
# NOT under /app: run_in_container.sh bind-mounts the host repo over /app
# (same as every sibling sandbox), which would shadow anything baked in
# there at image-build time. Discovered when this item's first compute run
# hit FileNotFoundError on a checkpoint the build step had just verified
# existed — /models sits outside the bind mount so it survives.
COPY experiments/whisperx_vad/vad_pytorch_model.bin /models/whisperx_vad/pytorch_model.bin
ARG WHISPERX_VAD_CHECKPOINT_SHA256="0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea"
RUN echo "${WHISPERX_VAD_CHECKPOINT_SHA256}  /models/whisperx_vad/pytorch_model.bin" | sha256sum -c -
