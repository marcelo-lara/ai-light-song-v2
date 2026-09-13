# Research sandbox for the SVD Tagger experiment ("svd_tagger", v3.5).
#
# PANNs (Kong et al., Cnn14) — a general AudioSet-527 tagger's `Singing`
# class head, run on the vocal stem and on the mix. PANNs was chosen over
# BEATs: smaller, a stable pretrained checkpoint, well-documented
# Singing/Music output classes, narrower dependency footprint than BEATs'
# fairseq-adjacent stack.
#
# Originally pinned to the CPU wheel index — running on CPU sidesteps any
# torch/CUDA compatibility question entirely, and this item's job was to
# prove the pipeline works, not to be fast. Switched to the CUDA 12.1 wheel
# (`cu121`, verified present for torch/torchaudio 2.4.1 at
# download.pytorch.org/whl/torch/) to speed up the corpus-wide run on the
# host's GTX 1650 (Turing, sm_75 — supported by every cu11x/cu12x torch
# build). Same exact torch/torchaudio version (2.4.1) either way — only the
# wheel variant changed. GPU is opt-in via `--device cuda` (see run.py); the
# default stays "cpu" so existing CPU-only invocations are unaffected.
# `CUDA_VISIBLE_DEVICES`/`SVD_TAGGER_DEVICE` no longer hard-disable the GPU
# at the container level (removed below).
#
# The checkpoint is fetched and sha256-checksummed HERE, at image build time.
# No download ever happens at analysis time — `model.py` loads the
# checkpoint from the fixed path this Dockerfile bakes in
# (/opt/panns/Cnn14_mAP=0.431.pth) and fails loudly if it is missing, never
# falls back to `panns_inference`'s own auto-download. Deliberately outside
# /app: `run_in_container.sh` bind-mounts the host repo onto /app, which
# would otherwise shadow anything baked into that path at build time.
FROM ai-light-song-v2:dev

ENV PYTHONPATH=/app \
    TOKENIZERS_PARALLELISM=false

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu121 \
      "torch==2.4.1" "torchaudio==2.4.1"

RUN pip install --no-cache-dir \
      "numpy<2" \
      "panns-inference==0.1.1" \
      "librosa>=0.10" \
      "soundfile" \
 && pip install --no-cache-dir --force-reinstall \
      --index-url https://download.pytorch.org/whl/cu121 "torch==2.4.1" "torchaudio==2.4.1" \
 && pip install --no-cache-dir --force-reinstall "numpy<2"

# --- pinned checkpoint, fetched + checksummed at BUILD time -----------------
# Source: Zenodo record 3987831 (qiuqiangkong/audioset_tagging_cnn's own
# canonical PANNs release; the same file panns_inference's default
# checkpoint_path resolves to at /root/panns_data/Cnn14_mAP=0.431.pth).
# Hash computed by downloading the file directly and running sha256sum on it
# this session — not copied from a third party's claim, verified first-hand.
ARG PANNS_CHECKPOINT_URL="https://zenodo.org/records/3987831/files/Cnn14_mAP=0.431.pth"
ARG PANNS_CHECKPOINT_SHA256="0dc499e40e9761ef5ea061ffc77697697f277f6a960894903df3ada000e34b31"
RUN mkdir -p /opt/panns \
 && curl -fL --retry 3 -o "/opt/panns/Cnn14_mAP=0.431.pth" "$PANNS_CHECKPOINT_URL" \
 && echo "${PANNS_CHECKPOINT_SHA256}  /opt/panns/Cnn14_mAP=0.431.pth" | sha256sum -c -

# --- pinned AudioSet-527 label index, fetched + checksummed at BUILD time ---
# `panns_inference.config` reads this from `~/panns_data/class_labels_indices.csv`
# and, if absent, shells out to `wget` (not installed in this image, and a
# mid-run download either way) to fetch it from the same Google Research URL
# pinned here. Baking it in at build time matches the checkpoint above and
# keeps analysis-time behavior offline and deterministic. Hash verified
# directly (not copied from a third party's claim) — see `model.py`'s
# "Class index" docstring section for the row-27 "Singing" cross-check.
ARG PANNS_LABELS_URL="http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv"
ARG PANNS_LABELS_SHA256="cdd1049833c4b86127c2773ac0d14a2754b6a6d0d1798002ed5c66e699708429"
RUN mkdir -p /root/panns_data \
 && curl -fL --retry 3 -o "/root/panns_data/class_labels_indices.csv" "$PANNS_LABELS_URL" \
 && echo "${PANNS_LABELS_SHA256}  /root/panns_data/class_labels_indices.csv" | sha256sum -c -
