# syntax=docker/dockerfile:1.7

FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

ARG ESSENTIA_REF=8da4f17c7fa2e748b6cde70a0438675d84c8c089
ARG TENSORFLOW_VERSION=2.12.1
ARG OMNIZART_DRUM_CHECKPOINT_URL=https://github.com/Music-and-Culture-Technology-Lab/omnizart/releases/download/checkpoints-20211001/drum_keras@variables.data-00000-of-00001

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    LD_LIBRARY_PATH=/usr/local/lib/tensorflow-wheel-libs:/usr/local/lib:/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:${LD_LIBRARY_PATH}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    python-is-python3 \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    git \
    curl \
    ca-certificates \
    patchelf \
    build-essential \
    pkg-config \
    libfluidsynth3 \
    libeigen3-dev \
    libyaml-dev \
    libfftw3-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    libsamplerate0-dev \
    libtag1-dev \
    libchromaprint-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/build
COPY requirements.txt ./requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python3 -m pip install --upgrade pip setuptools wheel poetry-core Cython && \
    python3 -m pip install 'numpy<2' && \
    grep -Ev '^(git\+https://github.com/audiohacking/omnizart.git|torch==2.1.2|torchaudio==2.1.2)$' requirements.txt > /tmp/build/requirements.core.txt && \
    python3 -m pip install --no-build-isolation -r /tmp/build/requirements.core.txt && \
    python3 -m pip install --index-url https://download.pytorch.org/whl/cu118 torch==2.1.2 torchaudio==2.1.2 && \
    python3 -m pip install --no-deps git+https://github.com/audiohacking/omnizart.git && \
    python3 -m pip install --no-deps resampy==0.4.3 && \
    PYTHON_SITE_PACKAGES="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" && \
    git init /tmp/build/essentia-src && \
    cd /tmp/build/essentia-src && \
    git remote add origin https://github.com/MTG/essentia.git && \
    git fetch --depth 1 origin "$ESSENTIA_REF" && \
    git checkout --detach FETCH_HEAD && \
    src/3rdparty/tensorflow/setup_from_python.sh && \
    python3 waf configure \
        --build-static \
        --with-python \
        --with-tensorflow \
        --prefix=/usr/local \
        --pythondir="$PYTHON_SITE_PACKAGES" && \
    python3 waf -j"$(nproc)" && \
    python3 waf install && \
    rm -rf /tmp/build/essentia-src && \
    ldconfig

RUN curl -L -o /tmp/build/libtensorflow.tar.gz "https://storage.googleapis.com/tensorflow/libtensorflow/libtensorflow-gpu-linux-x86_64-${TENSORFLOW_VERSION}.tar.gz" && \
    tar -C /usr/local -xzf /tmp/build/libtensorflow.tar.gz && \
    PYTHON_SITE_PACKAGES="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" && \
    ESSENTIA_EXTENSION="$(find "$PYTHON_SITE_PACKAGES/essentia" -maxdepth 1 -name '_essentia*.so' -print -quit)" && \
    patchelf --add-needed libtensorflow.so.2 "$ESSENTIA_EXTENSION" && \
    mkdir -p /usr/local/lib/tensorflow-wheel-libs && \
    TENSORFLOW_FRAMEWORK_LIB="$(find "$PYTHON_SITE_PACKAGES/tensorflow" -type f -name 'libtensorflow_framework.so*' -print -quit)" && \
    TENSORFLOW_CC_LIB="$(find "$PYTHON_SITE_PACKAGES/tensorflow" -type f -name 'libtensorflow_cc.so*' -print -quit)" && \
    ln -sf "$TENSORFLOW_FRAMEWORK_LIB" /usr/local/lib/tensorflow-wheel-libs/ && \
    ln -sf "$TENSORFLOW_CC_LIB" /usr/local/lib/tensorflow-wheel-libs/ && \
    OMNIZART_PACKAGE_DIR="$(python3 -c 'from importlib import util; from pathlib import Path; spec = util.find_spec("omnizart"); print(Path(next(iter(spec.submodule_search_locations))))')" && \
    mkdir -p "$OMNIZART_PACKAGE_DIR/checkpoints/drum/drum_keras/variables" && \
    curl -L "$OMNIZART_DRUM_CHECKPOINT_URL" -o "$OMNIZART_PACKAGE_DIR/checkpoints/drum/drum_keras/variables/variables.data-00000-of-00001" && \
    rm -f /tmp/build/libtensorflow.tar.gz && \
    ldconfig

RUN python3 - <<'PY'
from importlib import util
from pathlib import Path

spec = util.find_spec("omnizart")
if spec is None or not spec.submodule_search_locations:
    raise SystemExit("omnizart package not installed")

package_dir = Path(next(iter(spec.submodule_search_locations)))
model_dir = package_dir / "checkpoints" / "drum" / "drum_keras"
required = [
    model_dir / "saved_model.pb",
    model_dir / "variables" / "variables.index",
    model_dir / "variables" / "variables.data-00000-of-00001",
    model_dir / "configurations.yaml",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(f"Omnizart drum checkpoint incomplete: {missing}")
PY

WORKDIR /app
RUN mkdir -p /data

CMD ["bash"]