# XPU: TTS migrated from ElevenLabs (cloud) to local Parler-TTS. This base
# installs Parler-TTS + CPU PyTorch, which is portable to any host. TTS runs
# on CPU by default (TTS_DEVICE=cpu / auto). To run Parler-TTS on an Intel
# GPU instead, use a base image whose Level Zero user-mode driver matches the
# host GPU kernel driver and set TTS_DEVICE=xpu — see XPU_MIGRATION.md.
FROM python:3.11-slim

USER root
ARG DEBIAN_FRONTEND=noninteractive

RUN set -x \
    && apt-get update \
    && apt-get -y install wget curl git build-essential \
    && apt-get install -y sox libsox-fmt-all libsox-fmt-mp3 libsndfile1-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /workspace

RUN pip install --no-cache-dir \
    fastapi uvicorn pydantic redis httpx \
    soundfile numpy \
    parler-tts \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-requests \
    opentelemetry-instrumentation-redis \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-instrumentation-httpx \
    opentelemetry-instrumentation-urllib3 \
    ujson

# Copy shared package first
COPY shared /shared
RUN pip install /shared

# Copy service files
COPY services/TTSService/main.py ./

EXPOSE 8889

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8889"]
