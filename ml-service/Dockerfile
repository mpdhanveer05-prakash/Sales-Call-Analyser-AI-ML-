FROM python:3.11-slim-bullseye

# Bullseye ships FFmpeg 4.3.x — avoids the AV_OPT_TYPE_CHANNEL_LAYOUT API break in FFmpeg 5.1+
# pkg-config + dev headers are needed for PyAV (av==10.*) source build
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

# PyTorch CPU-only — install before everything else so it doesn't pull in GPU torch
RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# av==10.0.0 (required by faster-whisper 0.10.1) is incompatible with Cython 3.x.
# Pre-install Cython<3.0 then build av WITHOUT pip's isolated build env so it
# uses our pinned Cython instead of letting pip fetch Cython 3.x automatically.
RUN pip install --no-cache-dir "Cython>=0.29.31,<3.0" && \
    pip install --no-cache-dir "av==10.0.0" --no-build-isolation

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy English model — direct wheel avoids broken URL from `spacy download`
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# Whisper + sentence-transformer models download here on first request
RUN mkdir -p /app/model_cache

COPY app/ ./app/

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]
