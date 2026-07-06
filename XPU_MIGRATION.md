# Running pdf-to-podcast on Intel GPUs (XPU)

This branch ports the NVIDIA-AI-Blueprints `pdf-to-podcast` stack from
NVIDIA/CUDA + cloud services to **Intel Arc Pro GPUs**
using upstream vLLM-XPU. The diff against `main` is the "what to change"
comparison; this document explains each change and how to run it.

The migration is **not a CUDA-kernel port** — the repo has no `torch.cuda`
call sites. It is an *infrastructure / provider swap*: the GPU work is the
LLM, which moves from the NVIDIA NIM cloud API to a local vLLM-XPU endpoint;
the rest is base-image, dependency, and config changes.

## What changed and why

| Area | Upstream (NVIDIA) | This branch (XPU) | Why |
|---|---|---|---|
| LLM inference | NVIDIA NIM cloud (`integrate.api.nvidia.com`), `nvidia/llama-3.3-nemotron-super-49b` | Local **vLLM-XPU** serving `meta-llama/Llama-3.1-8B-Instruct` | Run on-prem on Intel GPU; the 49B model does not fit a single card |
| LLM client (`shared/shared/llmmanager.py`) | `ChatNVIDIA` only | `ChatOpenAI` for local endpoints, `ChatNVIDIA` for remote | `ChatNVIDIA.with_structured_output()` does not forward `response_format: json_schema` to a generic endpoint; the outline/dialogue steps need it |
| `models.json` | NIM model + cloud `api_base` | Local model name + `http://host.docker.internal:8100/v1` | Point the app at the local vLLM-XPU server |
| PDF service base image (`Dockerfile.api/.worker`) | `pytorch/pytorch:*-cuda*` | `python:3.11-slim` | No GPU work in this service; drops the CUDA runtime |
| `requirements.worker.txt` | `docling==2.2.0` (pinned) | `docling>=2.5.0` | 2.2.0 imports a symbol removed in `docling-core` 2.x |
| Docling OCR (`tasks.py`) | default (OCR on) | `do_ocr=False` | docling >= 2.5 downloads a RapidOCR model at runtime; fails offline. Text-native PDFs need no OCR |
| TTS (`services/TTSService`) | ElevenLabs cloud API | Local **Parler-TTS** | Fully local, no third-party API key |
| `shared/setup.py`, AgentService Dockerfile | `langchain-nvidia-ai-endpoints` | + `langchain-openai` | Dependency for the local `ChatOpenAI` path |
| `docker-compose.yaml` | cloud keys, no device/proxy | `host.docker.internal` gateway, TTS device/HF-cache/proxy env, local-key defaults | Reach the host vLLM server; portable env-driven config |

All host-specific values (proxy, model path, HF cache dir, device) are
**env-overridable** with defaults in `.env.xpu.example` — no source edits
needed to move between hosts.

## Prerequisites

- Docker with Intel GPU access on the host (`/dev/dri/renderD*` present; user
  in the `render`/`video` groups).
- An Intel Arc Pro GPU with enough VRAM for Llama-3.1-8B at bf16 (~16 GB).
- The LLM weights cached locally (default `/data/llm-models/Llama-3.1-8B-Instruct`).
- A vLLM-XPU image that can enumerate the host GPU (default
  `aicssdev/vllm-xpu:main-fe57be780`).

## Run it

```sh
# 1. Config
cp .env.xpu.example .env          # edit if your host differs from the defaults

# 2. Start the LLM endpoint on the Intel GPU (serves on host port 8100)
bash scripts/xpu/start-vllm-xpu.sh

# 3. Build + start the application stack
# On a proxied / air-gapped host, the HTTP(S)_PROXY values in .env are passed
# to the image builds automatically (compose build args), so apt/pip can reach
# the internet. On a direct-internet host, leave those blank.
docker compose --env-file .env up -d --build

# 4. Generate a podcast (5-page text PDF example)
JOB=$(curl -s -X POST http://localhost:8002/process_pdf \
  -F "target_files=@/path/to/your.pdf" \
  -F 'transcription_params={"userId":"me","name":"My Podcast","duration":2,
      "monologue":true,"speaker_1_name":"Alex",
      "voice_mapping":{"speaker-1":"speaker-1"},"guide":"Keep it short."}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')

# 5. Poll, then download
curl -s "http://localhost:8002/status/$JOB?userId=me" | python3 -m json.tool
curl "http://localhost:8002/output/$JOB?userId=me" -o podcast.mp3
```

## Notes

- **TTS runs on CPU by default** (`TTS_DEVICE=cpu`). Parler-TTS mini on CPU
  synthesizes ~5 segments/min, so a long podcast takes a while — it is the
  pipeline's slowest stage. To run TTS on an Intel GPU, `main.py` already
  auto-detects XPU (`TTS_DEVICE=xpu` or `auto`), but the TTS image's Level
  Zero user-mode driver must match the host GPU kernel driver, or
  `torch.xpu.is_available()` returns False and it silently uses CPU. Rebuild
  `services/TTSService/Dockerfile` on a matching base to enable it.
- **All four render nodes** are passed to the vLLM container even for
  single-card use; Level Zero needs the full enumeration surface (see the
  launcher script comment).
- The default model fits one card. For larger models, raise
  `ZE_AFFINITY_MASK` to multiple cards and add `--tensor-parallel-size` in the
  launcher.
