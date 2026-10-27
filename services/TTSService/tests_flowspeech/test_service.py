"""Offline checks of the actual service methods without Redis, telemetry, or paid APIs."""

import ast
import asyncio
import contextlib
import io
import os
import types
import wave
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from flowspeech import (
    FlowSpeechAudio,
    FlowSpeechClient,
    dialogue_segments,
    pcm_to_wav,
    request_id_for_job,
)
from test_v1_contract import JOB, REQUEST, Clock, job, response, wav_bytes

ROOT = Path(os.environ.get("FLOWSPEECH_TEST_ROOT", Path(__file__).resolve().parents[1]))


def request_models(provider="flowspeech"):
    namespace = {
        "BaseModel": BaseModel,
        "ConfigDict": ConfigDict,
        "TTS_PROVIDER": provider,
        "List": List,
        "Dict": Dict,
        "Optional": Optional,
        "DEFAULT_VOICE_1": "Kore",
        "DEFAULT_VOICE_2": "Puck",
    }
    tree = ast.parse((ROOT / "main.py").read_text())
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name in ("DialogueEntry", "TTSRequest")
    ]
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "main.py"), "exec"),
        namespace,
    )
    return namespace["TTSRequest"]


@pytest.mark.parametrize("field", ["model", "source", "speed", "format", "speakers"])
def test_actual_request_model_rejects_unknown_fields(field):
    with pytest.raises(ValidationError):
        request_models()(
            job_id="test",
            dialogue=[{"speaker": "speaker-1", "text": "Hello"}],
            **{field: "unsupported"},
        )


@pytest.mark.parametrize(
    "dialogue",
    [
        [{"speaker": "speaker-1", "text": 123}],
        [{"speaker": "speaker-1", "text": "Hello", "speed": 2}],
        [{"speaker": "speaker-1", "text": "Hello", "voice_id": False}],
        "not a list",
    ],
)
def test_actual_request_model_rejects_malformed_turns(dialogue):
    with pytest.raises(ValidationError):
        request_models()(job_id="test", dialogue=dialogue)


def test_other_provider_model_retains_extra_field_behavior():
    value = request_models("other")(job_id="test", dialogue=[], unused_option=True)
    assert value.job_id == "test"


def entry(text="Hello", speaker="speaker-1", voice_id=None):
    return types.SimpleNamespace(text=text, speaker=speaker, voice_id=voice_id)


def adapter(handler, clock=None):
    clock = clock or Clock()
    api = httpx.Client(transport=httpx.MockTransport(handler))
    audio = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=wav_bytes())
        )
    )
    client = FlowSpeechClient(
        "test-only",
        httpx_client=api,
        download_client=audio,
        clock=clock,
        sleep=clock.sleep,
    )
    return client, api, audio


def test_single_convert_keeps_pcm_interface_and_job_ids():
    calls = []

    def handle(request):
        calls.append(request)
        return response(job())

    client, api, download = adapter(handle)
    with api, download, client:
        audio = client.convert("Hello", "Kore", request_id=REQUEST)
    assert audio.pcm == b"\0\0" * 24
    assert (audio.sample_rate, audio.channels, audio.bits_per_sample) == (24000, 1, 16)
    assert audio.job_id == JOB and audio.request_id == REQUEST
    assert pcm_to_wav(audio) == wav_bytes()
    assert len(calls) == 1 and calls[0].headers["Idempotency-Key"] == REQUEST


@pytest.mark.parametrize(
    "audio",
    [
        FlowSpeechAudio(b"", 24000, 1, 16),
        FlowSpeechAudio(b"x", 24000, 1, 16),
        FlowSpeechAudio(b"xx", 48000, 1, 16),
    ],
)
def test_compatibility_encoder_rejects_invalid_pcm(audio):
    with pytest.raises(RuntimeError):
        pcm_to_wav(audio)


def test_service_request_uuid_is_stable_and_input_independent():
    assert request_id_for_job("service-42") == request_id_for_job("service-42")
    assert request_id_for_job("service-42") != request_id_for_job("service-43")
    with pytest.raises(ValueError):
        request_id_for_job("")


def test_dialogue_mapping_has_no_silent_voice_fallback():
    turns = [entry(), entry("Reply", "speaker-2", "Puck"), entry("Again")]
    assert dialogue_segments(turns, {"speaker-1": "Kore", "speaker-2": "Puck"}) == [
        {"speaker": "speaker-1", "text": "Hello", "voiceName": "Kore"},
        {"speaker": "speaker-2", "text": "Reply", "voiceName": "Puck"},
        {"speaker": "speaker-1", "text": "Again", "voiceName": "Kore"},
    ]
    with pytest.raises(ValueError):
        dialogue_segments([entry(speaker="unknown")], {"speaker-1": "Kore"})
    with pytest.raises(ValueError):
        dialogue_segments([entry(), entry(voice_id="Puck")], {"speaker-1": "Kore"})


def service_namespace():
    updates, created = [], []

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code, self.detail = status_code, detail

    span = types.SimpleNamespace(set_attribute=lambda *args: None)
    telemetry = types.SimpleNamespace(
        tracer=types.SimpleNamespace(
            start_as_current_span=lambda _: contextlib.nullcontext(span)
        )
    )
    ns = {
        "asyncio": asyncio,
        "lru_cache": lru_cache,
        "List": List,
        "Dict": Dict,
        "VoiceInfo": lambda **kwargs: types.SimpleNamespace(**kwargs),
        "DialogueEntry": object,
        "TTSRequest": object,
        "BackgroundTasks": object,
        "HTTPException": HTTPException,
        "TTS_PROVIDER": "flowspeech",
        "dialogue_segments": dialogue_segments,
        "pcm_to_wav": pcm_to_wav,
        "request_id_for_job": request_id_for_job,
        "telemetry": telemetry,
        "job_manager": types.SimpleNamespace(
            update_status=lambda *args: updates.append(args),
            create_job=lambda *args: created.append(args),
        ),
        "JobStatus": types.SimpleNamespace(PROCESSING="processing"),
        "DEFAULT_VOICE_MAPPING": {"speaker-1": "Kore", "speaker-2": "Puck"},
    }
    tree = ast.parse((ROOT / "main.py").read_text())
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef))
        and node.name in ("TTSService", "generate_tts")
    ]
    for node in nodes:
        node.decorator_list = []
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "main.py"), "exec"),
        ns,
    )
    return ns, updates, created


def test_actual_service_batches_ordered_dialogue_into_one_paid_job():
    request_id = request_id_for_job("service-42")
    calls = []

    def handle(request):
        calls.append(request)
        return response(job(requestId=request_id))

    client, api, download = adapter(handle)
    ns, updates, _ = service_namespace()
    service = object.__new__(ns["TTSService"])
    service.flow_speech_client = client
    with api, download, client, ThreadPoolExecutor(max_workers=1) as pool:
        service.thread_pool = pool
        result = asyncio.run(
            service._process_dialogue(
                "service-42",
                [entry(), entry("Reply", "speaker-2")],
                {"speaker-1": "Kore", "speaker-2": "Puck"},
            )
        )
    assert len(calls) == 1
    assert calls[0].headers["Idempotency-Key"] == request_id
    import json

    payload = json.loads(calls[0].content)
    assert (
        payload["input"]["mode"] == "multi" and len(payload["input"]["segments"]) == 2
    )
    assert request_id in updates[0][2]
    assert result == wav_bytes()
    with wave.open(io.BytesIO(result), "rb") as audio:
        assert audio.getnchannels() == 1 and audio.getnframes() == 24


def test_actual_endpoint_returns_request_id_before_background_submission():
    ns, _, created = service_namespace()
    queued = []
    request = types.SimpleNamespace(
        dialogue=[entry()], job_id="service-42", voice_mapping={"speaker-1": "Kore"}
    )
    ns["tts_service"] = types.SimpleNamespace(process_job=lambda *args: None)
    result = asyncio.run(
        ns["generate_tts"](
            request, types.SimpleNamespace(add_task=lambda *args: queued.append(args))
        )
    )
    assert result == {
        "job_id": "service-42",
        "flowspeech_request_id": request_id_for_job("service-42"),
    }
    assert len(queued) == len(created) == 1


def test_actual_endpoint_rejects_invalid_dialogue_before_queuing():
    ns, _, created = service_namespace()
    request = types.SimpleNamespace(
        dialogue=[], job_id="service-42", voice_mapping=None
    )
    with pytest.raises(ns["HTTPException"]) as caught:
        asyncio.run(ns["generate_tts"](request, None))
    assert caught.value.status_code == 422 and not created


def test_actual_service_uses_live_voice_catalog():
    calls = []

    def handle(request):
        calls.append(request)
        return response({"voices": [{"name": "FreshVoice", "description": "Current"}]})

    client, api, download = adapter(handle)
    ns, _, _ = service_namespace()
    service = object.__new__(ns["TTSService"])
    service.flow_speech_client = client
    with api, download, client:
        voices = service.get_available_voices()
    assert [v.voice_id for v in voices] == ["FreshVoice"]
    assert calls[0].url.path == "/api/v1/voices"


def test_existing_other_service_branch_is_unchanged():
    ns, _, _ = service_namespace()
    service = object.__new__(ns["TTSService"])
    service.flow_speech_client = None
    service.eleven_labs_client = types.SimpleNamespace(
        text_to_speech=types.SimpleNamespace(
            convert=lambda **kwargs: iter([b"mp3", b"audio"])
        )
    )
    assert service._convert_text("Hello", "voice") == b"mp3audio"


def test_container_copies_both_runtime_modules():
    docker = (ROOT / "Dockerfile").read_text()
    for name in ("flowspeech.py", "flowspeech_v1.py"):
        assert f"COPY services/TTSService/{name} ./" in docker
