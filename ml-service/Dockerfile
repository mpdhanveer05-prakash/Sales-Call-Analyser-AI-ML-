# Stage 1: extract CUDA + cuDNN runtime libraries only — no apt-get needed
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS cuda-libs

# Stage 2: main build — python:3.11-slim-bullseye (all pip layers already cached)
# cuDNN libraries are copied in from stage 1, no Ubuntu apt-get slowness
FROM python:3.11-slim-bullseye

# Copy CUDA runtime + cuDNN + cuBLAS libraries from stage 1
COPY --from=cuda-libs /usr/local/cuda-12.1/lib64/ /usr/local/cuda/lib64/
COPY --from=cuda-libs /usr/lib/x86_64-linux-gnu/libcudnn*.so* /usr/lib/x86_64-linux-gnu/
COPY --from=cuda-libs /usr/lib/x86_64-linux-gnu/libcublas*.so* /usr/lib/x86_64-linux-gnu/
COPY --from=cuda-libs /usr/lib/x86_64-linux-gnu/libcufft*.so* /usr/lib/x86_64-linux-gnu/

ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH

RUN ldconfig

# Bullseye ships FFmpeg 4.3.x — avoids the AV_OPT_TYPE_CHANNEL_LAYOUT API break in FFmpeg 5.1+
RUN apt-get update && apt-get install -y --no-install-recommends \
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

WORKDIR /app

# PyTorch CPU-only — sentence-transformers runs on CPU.
# GPU acceleration for Whisper comes via CTranslate2 + cuDNN, not PyTorch.
RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# av==10.0.0 (required by faster-whisper 0.10.1) is incompatible with Cython 3.x.
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
