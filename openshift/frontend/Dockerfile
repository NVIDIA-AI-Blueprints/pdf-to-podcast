FROM registry.access.redhat.com/ubi9/python-311

WORKDIR /app

# Install Python packages needed by frontend
# Pin versions to match local working environment
RUN pip install --no-cache-dir \
    gradio==6.10.0 \
    huggingface_hub==1.8.0 \
    requests \
    websockets \
    ujson

# Copy shared package first (chown for non-root UBI user)
COPY --chown=1001:0 shared /shared
RUN pip install /shared

# Copy frontend files
COPY frontend /app/frontend

WORKDIR /app

CMD ["python3", "-m", "frontend"]
