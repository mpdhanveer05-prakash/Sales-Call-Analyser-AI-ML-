# NVIDIA CUDA 12.4 + cuDNN 9 — required for faster-whisper GPU inference
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Python 3.11 via deadsnakes PPA + FFmpeg
# Ubuntu 22.04 ships FFmpeg 4.4.x — safe, avoids the AV_OPT_TYPE_CHANNEL_LAYOUT API break in FFmpeg 5.1+
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    curl \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3.11-distutils \
    ffmpeg \
    build-essential \
    pkg-config \
    libavcodec-dev \
    libavdevice-dev \
    libavfilter-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

# Set python3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

WORKDIR /app

# PyTorch CPU build — sentence-transformers runs fine on CPU.
# GPU acceleration for Whisper comes via CTranslate2 + cuDNN, not PyTorch.
RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# av==10.0.0 (required by faster-whisper 0.10.1) is incompatible with Cython 3.x.
# Pre-install Cython<3.0 then build av WITHOUT pip's isolated build env.
RUN pip install --no-cache-dir "Cython>=0.29.31,<3.0" && \
    pip install --no-cache-dir "av==10.0.0" --no-build-isolation

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# spaCy English model
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# Whisper + sentence-transformer models download here on first request
RUN mkdir -p /app/model_cache

COPY app/ ./app/

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]
