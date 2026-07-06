from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import os
import io
import soundfile as sf
import numpy as np
import torch
from shared.api_types import ServiceType, JobStatus
from shared.job import JobStatusManager
from shared.otel import OpenTelemetryInstrumentation, OpenTelemetryConfig
from opentelemetry.trace.status import StatusCode
from concurrent.futures import ThreadPoolExecutor
import asyncio
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Parler-TTS Service", debug=True)
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "2"))
TTS_MODEL_NAME = os.getenv("TTS_MODEL", "parler-tts/parler-tts-mini-v1")
TTS_DEVICE = os.getenv("TTS_DEVICE", "auto")

VOICE_DESCRIPTIONS = {
    "speaker-1": "A male speaker with a warm, clear voice delivers the text at a moderate pace in a studio-quality recording.",
    "speaker-2": "A female speaker with an expressive, engaging voice narrates clearly and confidently.",
}

telemetry = OpenTelemetryInstrumentation()
config = OpenTelemetryConfig(
    service_name="tts-service",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://jaeger:4317"),
    enable_redis=True,
    enable_requests=True,
)
telemetry.initialize(config, app)

job_manager = JobStatusManager(ServiceType.TTS, telemetry=telemetry)


class DialogueEntry(BaseModel):
    text: str
    speaker: str
    voice_id: Optional[str] = None


class TTSRequest(BaseModel):
    dialogue: List[DialogueEntry]
    job_id: str
    scratchpad: Optional[str] = ""
    voice_mapping: Optional[Dict[str, str]] = {}


class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    description: Optional[str] = None


def _select_device() -> str:
    if TTS_DEVICE != "auto":
        return TTS_DEVICE
    if torch.xpu.is_available():
        return "xpu"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class TTSService:
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS)
        self.device = _select_device()
        logger.info(f"TTS running on device: {self.device}")
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        if self._model is not None:
            return
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer
        logger.info(f"Loading Parler-TTS model: {TTS_MODEL_NAME}")
        self._tokenizer = AutoTokenizer.from_pretrained(TTS_MODEL_NAME)
        self._model = ParlerTTSForConditionalGeneration.from_pretrained(
            TTS_MODEL_NAME, torch_dtype=torch.float32
        ).to(self.device)
        self._model.eval()
        logger.info("Parler-TTS model loaded")

    @lru_cache(maxsize=1)
    def get_available_voices(self) -> List[VoiceInfo]:
        return [
            VoiceInfo(voice_id="speaker-1", name="Male Speaker", description=VOICE_DESCRIPTIONS["speaker-1"]),
            VoiceInfo(voice_id="speaker-2", name="Female Speaker", description=VOICE_DESCRIPTIONS["speaker-2"]),
        ]

    def _convert_text(self, text: str, speaker: str) -> bytes:
        self._load_model()
        description = VOICE_DESCRIPTIONS.get(speaker, VOICE_DESCRIPTIONS["speaker-1"])
        input_ids = self._tokenizer(description, return_tensors="pt").input_ids.to(self.device)
        prompt_ids = self._tokenizer(text, return_tensors="pt").input_ids.to(self.device)
        with torch.no_grad():
            generation = self._model.generate(
                input_ids=input_ids,
                prompt_input_ids=prompt_ids,
                do_sample=True,
                temperature=1.0,
            )
        if self.device == "xpu":
            torch.xpu.synchronize()
        audio_arr = generation.cpu().numpy().squeeze()
        sample_rate = self._model.config.sampling_rate
        buf = io.BytesIO()
        sf.write(buf, audio_arr, sample_rate, format="mp3")
        return buf.getvalue()

    async def process_job(self, job_id: str, request: TTSRequest):
        with telemetry.tracer.start_as_current_span("tts.process_job") as span:
            try:
                job_manager.update_status(job_id, JobStatus.PROCESSING, f"Processing {len(request.dialogue)} dialogue entries")
                combined_audio = await self._process_dialogue(job_id, request.dialogue)
                job_manager.set_result(job_id, combined_audio)
                job_manager.update_status(job_id, JobStatus.COMPLETED, "Audio generation completed successfully")
            except Exception as e:
                logger.error(f"Error processing job {job_id}: {str(e)}")
                job_manager.update_status(job_id, JobStatus.FAILED, str(e))
                span.set_status(StatusCode.ERROR)

    async def _process_dialogue(self, job_id: str, dialogue: List[DialogueEntry]) -> bytes:
        combined = b""
        for i, entry in enumerate(dialogue):
            job_manager.update_status(job_id, JobStatus.PROCESSING, f"Processing segment {i+1}/{len(dialogue)}")
            audio = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool, self._convert_text, entry.text, entry.speaker
            )
            combined += audio
        return combined


tts_service = TTSService()


@app.get("/voices")
async def list_voices() -> List[VoiceInfo]:
    return tts_service.get_available_voices()


@app.post("/generate_tts", status_code=202)
async def generate_tts(request: TTSRequest, background_tasks: BackgroundTasks):
    with telemetry.tracer.start_as_current_span("tts.generate_tts") as span:
        span.set_attribute("job_id", request.job_id)
        job_manager.create_job(request.job_id)
        background_tasks.add_task(tts_service.process_job, request.job_id, request)
        return {"job_id": request.job_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    with telemetry.tracer.start_as_current_span("tts.get_status") as span:
        span.set_attribute("job_id", job_id)
        status = job_manager.get_status(job_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Job not found")
        span.set_attribute("status", status.get("status"))
        return status


@app.get("/output/{job_id}")
async def get_output(job_id: str):
    with telemetry.tracer.start_as_current_span("tts.get_output") as span:
        span.set_attribute("job_id", job_id)
        result = job_manager.get_result(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found")
        return Response(content=result, media_type="audio/mpeg", headers={"Content-Disposition": "attachment; filename=output.mp3"})


@app.post("/cleanup")
async def cleanup_jobs():
    removed = job_manager.cleanup_old_jobs()
    return {"message": f"Removed {removed} old jobs"}


@app.get("/health")
async def health():
    voices = tts_service.get_available_voices()
    return {"status": "healthy", "available_voices": len(voices), "device": tts_service.device, "max_concurrent_requests": MAX_CONCURRENT_REQUESTS}
