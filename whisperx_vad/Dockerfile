# `whisperx` Compose service — whisperX's VAD front-end as its own pipeline
# stage (promoted from experiments/whisperx_vad/, v3.6 item 2). Built with
# `docker compose build whisperx`, run with `docker compose run --rm whisperx
# --song <path>` (Dockerfile carried forward unchanged from the research
# sandbox — same pins, same checkpoint).
#
# whisperX (Max Bain et al., https://github.com/m-bain/whisperX) pinned at
# 3.8.6 — its VAD front-end only, never its ASR/alignment/diarization path.
#
# --- why a NEW image (not the app image, not svd_tagger's) -----------------
# `transformers` is absent from the `app` image. whisperX 3.8.6 additionally
# pins `torch~=2.8.0` / `torchaudio~=2.8.0` — far newer than the app image's
# `torch==2.1.2` / CUDA 11.8 base (`requirements.txt`), so the app image
# cannot host it without breaking `natten==0.15.1+torch210cu121` (allin1's
# segmentation dependency, torch-2.1-only). Built off the CUDA 12.6 wheel
# index (`cu126`, torch/torchaudio/torchvision 2.8.0 / 0.23.0). GPU is opt-in
# via `--device cuda`; the default stays "cpu".
#
# --- the checkpoint: PRE-FETCHED ON THE HOST, COPY'd in, never curled ------
# `svd_tagger`'s Dockerfile curled its 327 MB PANNs checkpoint FROM INSIDE the
# build and stalled at ~154 KB/s, never completing within a 15-minute budget.
# This Dockerfile applies that lesson: whisperX's VAD segmentation checkpoint
# (17,719,103 bytes, NOT the gated pyannote/speaker-diarization-3.1 model —
# see model.py's docstring) was downloaded from the `v3.8.6` git tag on the
# HOST and sha256-verified there
# (0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea). It is
# NOT committed to git (`.gitignore`: no binary model checkpoints, matching
# the repo-wide `models/` convention) — fetch it on the host before building:
#
#   curl -sL -o whisperx_vad/vad_pytorch_model.bin \
#     https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/assets/pytorch_model.bin
#   sha256sum whisperx_vad/vad_pytorch_model.bin
#   # expect: 0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea
#
# `COPY`'d in below once present — no network access during `docker build`
# for the checkpoint either way, and none at analysis time (model.py loads it
# from this fixed baked-in path, never whisperX's own bundled copy or any
# Hugging Face URL).
FROM ai-light-song-v2:dev

ENV TOKENIZERS_PARALLELISM=false \
    HF_HUB_OFFLINE=1

# torch pinned to whisperX 3.8.6's own requirement (torch~=2.8.0,
# torchaudio~=2.8.0), overriding the base image's CUDA 11.8 / torch 2.1.2.
# cu126 wheel variant (see header) — same pinned version, GPU-capable build.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu126 \
      "torch==2.8.0" "torchaudio==2.8.0"

# whisperX itself. Pulls pyannote-audio>=4.0.0 (which pulls
# pytorch-lightning + torchmetrics + torchvision transitively — none of
# whisperx's own direct deps, but torchmetrics imports torchvision
# unconditionally at import time), transformers, huggingface-hub,
# faster-whisper/ctranslate2 (ASR path — unused here, but whisperX is one
# package and the VAD-only subset is not published separately), pandas,
# nltk. `HF_HUB_OFFLINE=1` (set above) makes any accidental Hugging Face Hub
# call at runtime fail loudly instead of silently reaching the network —
# this module touches the Hub only through a local file path, never a repo id.
#
# `pip install whisperx` alone resolves torch/torchaudio/torchvision off
# PyPI's default index (CUDA wheels), which is large and undesired. The
# first attempt at this Dockerfile force-reinstalled only torch/torchaudio
# from the CPU index afterward and left torchvision at its CUDA-resolved
# build — that ABI mismatch crashes on `import torchvision` ("operator
# torchvision::nms does not exist"). Fixed by force-reinstalling torchvision
# from the same CPU index alongside torch/torchaudio, pinned to the version
# whisperx's own pyproject.toml requires (torchvision~=0.23.0).
RUN pip install --no-cache-dir "whisperx==3.8.6" \
 && pip install --no-cache-dir --force-reinstall \
      --index-url https://download.pytorch.org/whl/cu126 \
      "torch==2.8.0" "torchaudio==2.8.0" "torchvision==0.23.0"

# --- pinned checkpoint, pre-fetched on the HOST, COPY'd (never curled) -----
# NOT under /app: docker-compose.yml bind-mounts the repo over /app (same as
# `app`/`mcp`), which would shadow anything baked in there at image-build
# time. /models sits outside the bind mount so it survives.
COPY whisperx_vad/vad_pytorch_model.bin /models/whisperx_vad/pytorch_model.bin
ARG WHISPERX_VAD_CHECKPOINT_SHA256="0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea"
RUN echo "${WHISPERX_VAD_CHECKPOINT_SHA256}  /models/whisperx_vad/pytorch_model.bin" | sha256sum -c -

# WORKDIR /app is already set by the base image; `python -m whisperx_vad`
# resolves the package from cwd, `analyzer.*` from PYTHONPATH=/app/src (also
# inherited, unchanged, from the base image).
ENTRYPOINT ["python", "-m", "whisperx_vad"]
