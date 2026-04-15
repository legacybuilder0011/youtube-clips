# ---- Dockerfile for the Viral Clip Generator backend ----
# Runs on Railway / Render / Fly / any container host.
FROM python:3.11-slim

# ffmpeg is required for cutting clips and burning captions.
# libgomp1 is needed by faster-whisper's CTranslate2 runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libgomp1 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python deps first so Docker layer caching works on code-only changes.
# Force a yt-dlp upgrade on every build so YouTube extractor fixes land
# without a manual rebuild — yt-dlp ships roughly weekly.
COPY requirements.txt ./
RUN pip install -r requirements.txt \
 && pip install --upgrade --no-cache-dir yt-dlp

# Copy the application.
COPY backend ./backend

# Data dir for downloads / clips / jobs. Note: Railway's filesystem is
# ephemeral — attach a volume and set DATA_DIR=/data for persistence.
RUN mkdir -p /app/data
ENV DATA_DIR=/app/data

EXPOSE 8000

# Railway / Render / Fly all inject PORT. Fall back to 8000 for local runs.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
