# Research sandbox for the song-dynamics model survey (MERT, CLAP, beat-this).
#
# Derived from the analyzer image so it reuses that CUDA base instead of
# pulling a second multi-GB stack. Nothing in src/ imports anything installed
# here; the pipeline image is deliberately left untouched.
#
# Note that `beat_this` pulls torch 2.13 in over the base image's 2.1.2. That
# is fine for everything in this image, but it is why `allin1` needs its own
# sandbox (see Dockerfile.allin1): allin1 requires natten 0.15, which is only
# built against torch 2.1.
FROM ai-light-song-v2:dev

ENV HF_HOME=/app/models/hf \
    TOKENIZERS_PARALLELISM=false

# transformers 4.44 is the last line that still works cleanly with numpy<2 and
# already ships ClapModel; MERT loads through trust_remote_code.
RUN pip install --no-cache-dir \
      "transformers==4.44.2" \
      "huggingface_hub==0.24.6" \
      "safetensors" \
      "nnAudio==0.3.2" \
      "scikit-learn"

RUN pip install --no-cache-dir "https://github.com/CPJKU/beat_this/archive/main.zip"
