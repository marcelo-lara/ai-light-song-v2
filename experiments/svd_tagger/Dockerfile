# Research sandbox for the SVD Tagger experiment (v3.5 item 6 —
# implementation-plan-v3.5.md "svd_tagger").
#
# PANNs (Kong et al., Cnn14) — a general AudioSet-527 tagger's `Singing`
# class head, run on the vocal stem and on the mix. D6.1 resolved PANNs over
# BEATs: smaller, a stable pretrained checkpoint, well-documented
# Singing/Music output classes, narrower dependency footprint than BEATs'
# fairseq-adjacent stack.
#
# Same CPU-torch pattern as the sibling Dockerfile.vocalparse /
# Dockerfile.acestep sandboxes: the base image's CUDA 11.8 / torch 2.1 is
# fine for Cnn14 (81M params, small by this repo's standards), but running
# on CPU sidesteps any torch/CUDA compatibility question entirely — this
# item's job is to prove the pipeline works, not to be fast.
#
# The checkpoint is fetched and sha256-checksummed HERE, at image build time.
# No download ever happens at analysis time — `model.py` loads the
# checkpoint from the fixed path this Dockerfile bakes in
# (/app/models/panns/Cnn14_mAP=0.431.pth) and fails loudly if it is missing,
# never falls back to `panns_inference`'s own auto-download.
FROM ai-light-song-v2:dev

ENV PYTHONPATH=/app \
    TOKENIZERS_PARALLELISM=false \
    SVD_TAGGER_DEVICE=cpu \
    CUDA_VISIBLE_DEVICES=""

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
      "torch==2.4.1" "torchaudio==2.4.1"

RUN pip install --no-cache-dir \
      "numpy<2" \
      "panns-inference==0.1.1" \
      "librosa>=0.10" \
      "soundfile" \
 && pip install --no-cache-dir --force-reinstall \
      --index-url https://download.pytorch.org/whl/cpu "torch==2.4.1" "torchaudio==2.4.1" \
 && pip install --no-cache-dir --force-reinstall "numpy<2"

# --- pinned checkpoint, fetched + checksummed at BUILD time -----------------
# Source: Zenodo record 3987831 (qiuqiangkong/audioset_tagging_cnn's own
# canonical PANNs release; the same file panns_inference's default
# checkpoint_path resolves to at /root/panns_data/Cnn14_mAP=0.431.pth).
# Hash computed by downloading the file directly and running sha256sum on it
# this session — not copied from a third party's claim, verified first-hand.
ARG PANNS_CHECKPOINT_URL="https://zenodo.org/records/3987831/files/Cnn14_mAP=0.431.pth"
ARG PANNS_CHECKPOINT_SHA256="0dc499e40e9761ef5ea061ffc77697697f277f6a960894903df3ada000e34b31"
RUN mkdir -p /app/models/panns \
 && curl -fL --retry 3 -o "/app/models/panns/Cnn14_mAP=0.431.pth" "$PANNS_CHECKPOINT_URL" \
 && echo "${PANNS_CHECKPOINT_SHA256}  /app/models/panns/Cnn14_mAP=0.431.pth" | sha256sum -c -
