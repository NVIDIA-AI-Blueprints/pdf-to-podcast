FROM python:3.11-slim

WORKDIR /app

# Install only the necessary Python packages
RUN pip install uv 
RUN uv pip install --system \
    fastapi \
    uvicorn \
    python-multipart \
    httpx \
    redis \
    asyncio \
    requests \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-requests \
    opentelemetry-instrumentation-redis \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-instrumentation-httpx \
    opentelemetry-instrumentation-urllib3 \
    ujson

# Copy shared package
COPY shared /shared
RUN uv pip install --system /shared

# Copy the service code
COPY services/PDFService/main.py ./

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]