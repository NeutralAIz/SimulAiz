FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for audio/TTS/vision
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ffmpeg espeak-ng libespeak-ng1 libsndfile1 \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY AGENTS.md ./AGENTS.md
COPY scenarios ./scenarios
COPY assets ./assets
COPY docs ./docs
COPY deploy ./deploy

RUN pip install --upgrade pip && pip install --no-cache-dir -e .[dev]

CMD ["python", "-m", "simulaiz"]
