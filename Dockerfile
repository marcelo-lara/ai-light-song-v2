# syntax=docker/dockerfile:1.7

FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ARG ESSENTIA_REF=8da4f17c7fa2e748b6cde70a0438675d84c8c089
ARG TENSORFLOW_VERSION=2.12.1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    LD_LIBRARY_PATH=/usr/local/lib

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    python-is-python3 \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    libsndfile1 \
    git \
    curl \
    ca-certificates \
    patchelf \
    build-essential \
    pkg-config \
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
    python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install -r requirements.txt && \
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

RUN curl -L -o /tmp/build/libtensorflow.tar.gz "https://storage.googleapis.com/tensorflow/libtensorflow/libtensorflow-cpu-linux-x86_64-${TENSORFLOW_VERSION}.tar.gz" && \
    tar -C /usr/local -xzf /tmp/build/libtensorflow.tar.gz && \
    PYTHON_SITE_PACKAGES="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" && \
    ESSENTIA_EXTENSION="$(find "$PYTHON_SITE_PACKAGES/essentia" -maxdepth 1 -name '_essentia*.so' -print -quit)" && \
    patchelf --add-needed libtensorflow.so.2 "$ESSENTIA_EXTENSION" && \
    rm -f /tmp/build/libtensorflow.tar.gz && \
    ldconfig

WORKDIR /app
RUN mkdir -p /data

CMD ["bash"]