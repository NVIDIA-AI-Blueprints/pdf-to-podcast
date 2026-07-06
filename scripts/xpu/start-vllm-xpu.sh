#!/usr/bin/env bash
# Start a vLLM-XPU OpenAI-compatible server for pdf-to-podcast on an Intel GPU.
# The app's models.json points at http://host.docker.internal:8100/v1, so this
# serves on host port 8100 by default.
#
# All host-specifics are env-overridable; defaults target a single Intel Arc
# Pro (B60) with the model cached under /data/llm-models.
#
#   VLLM_IMAGE      container image (must be able to enumerate the host GPU)
#   MODEL_PATH      path to the model weights (mounted read-only)
#   SERVED_NAME     --served-model-name (must match models.json "name")
#   VLLM_PORT       host port (default 8100)
#   ZE_AFFINITY_MASK  which card(s) to use (default 0)
#   MAX_MODEL_LEN   context length (default 16384)
set -euo pipefail

VLLM_IMAGE="${VLLM_IMAGE:-aicssdev/vllm-xpu:main-fe57be780}"
MODEL_PATH="${MODEL_PATH:-/data/llm-models/Llama-3.1-8B-Instruct}"
SERVED_NAME="${SERVED_NAME:-meta-llama/Llama-3.1-8B-Instruct}"
VLLM_PORT="${VLLM_PORT:-8100}"
NAME="${VLLM_CONTAINER_NAME:-pdf-podcast-vllm-xpu}"
ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-0}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"
DATA_MOUNT="${DATA_MOUNT:-/data}"

if [ ! -d "$MODEL_PATH" ]; then
  echo "ERROR: MODEL_PATH not found: $MODEL_PATH" >&2
  echo "  Download it first, or set MODEL_PATH to your cached weights." >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "Removing existing container $NAME"
  docker rm -f "$NAME" >/dev/null
fi

# Pass all four DRM render nodes: Level Zero needs the full enumeration
# surface even when ZE_AFFINITY_MASK restricts compute to one card. Passing
# only one node causes a SYCL "No device" crash after weights load.
DEV_ARGS=()
for n in /dev/dri/renderD*; do
  [ -e "$n" ] && DEV_ARGS+=(--device "$n:$n")
done

echo "Starting $NAME on card $ZE_AFFINITY_MASK, port $VLLM_PORT (model: $SERVED_NAME)"
docker run -d --name "$NAME" \
  "${DEV_ARGS[@]}" \
  --group-add video --group-add render \
  -v "$DATA_MOUNT:$DATA_MOUNT" \
  -p "${VLLM_PORT}:8000" \
  -e ZE_FLAT_DEVICE_HIERARCHY=COMPOSITE \
  -e ZE_AFFINITY_MASK="$ZE_AFFINITY_MASK" \
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
  -e SYCL_CACHE_PERSISTENT=1 \
  -e CCL_ATL_TRANSPORT=ofi \
  -e CCL_ZE_IPC_EXCHANGE=pidfd \
  -e VLLM_XPU_ENABLE_XPU_GRAPH=0 \
  "$VLLM_IMAGE" \
  "$MODEL_PATH" \
  --served-model-name "$SERVED_NAME" \
  --dtype bfloat16 --enforce-eager \
  --host 0.0.0.0 --port 8000 \
  --max-model-len "$MAX_MODEL_LEN"

echo "Waiting for the server to be ready on http://localhost:${VLLM_PORT}/v1/models ..."
for i in $(seq 1 30); do
  if curl -sf "http://localhost:${VLLM_PORT}/v1/models" >/dev/null 2>&1; then
    echo "READY after ~$((i*5))s:"
    curl -s "http://localhost:${VLLM_PORT}/v1/models"
    exit 0
  fi
  st=$(docker inspect -f '{{.State.Status}}' "$NAME" 2>/dev/null || echo gone)
  if [ "$st" != "running" ]; then
    echo "Container $st before ready — last logs:" >&2
    docker logs "$NAME" 2>&1 | tail -20 >&2
    exit 1
  fi
  sleep 5
done
echo "Timed out waiting for readiness; check: docker logs $NAME" >&2
exit 1
