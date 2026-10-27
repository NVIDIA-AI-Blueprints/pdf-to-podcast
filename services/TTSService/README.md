# TTS Service

Build from the repository root:

```bash
docker build -f services/TTSService/Dockerfile -t tts-service .
```

## FlowSpeech API v1

Set `TTS_PROVIDER=flowspeech`, `FLOWSPEECH_API_KEY`, and an active API
subscription with sufficient credits. Optional settings are
`FLOWSPEECH_BASE_URL` (an HTTPS origin, default `https://flowspeech.io`),
`FLOWSPEECH_TIMEOUT` (total seconds, default 300), and the two default voices
`DEFAULT_VOICE_1=Kore` and `DEFAULT_VOICE_2=Puck`.

The service submits the full dialogue as one ordered multi-speaker v1 job.
Explicit voice assignments are preserved; unknown assignments and inconsistent
voices for the same speaker fail rather than silently changing the audio.
The voice endpoint reads the current FlowSpeech catalog.

`POST /generate_tts` returns the service `job_id` and
`flowspeech_request_id` before background generation starts. The latter is
deterministically derived from the service job ID. Reprocessing an unchanged
service job reuses the exact UUID; changing text or voices requires a new service
job ID. Never reuse a job ID for changed content or generate a new ID merely
because a download failed.

## Recovery

Keep the accepted request ID. The service also records it in progress messages;
errors retain the request ID and any known remote job ID.

```python
import os
from services.TTSService.flowspeech import FlowSpeechClient, request_id_for_job

with FlowSpeechClient(os.environ["FLOWSPEECH_API_KEY"]) as speech:
    request_id = request_id_for_job("your-existing-service-job-id")
    job = speech.find_job(request_id)  # Read-only; never submits a recording.
    # speech.get_job(remote_job_id) is also read-only.
    if job["status"] == "success" and not job.get("resultDeleted"):
        wav = speech.download_audio(job["result"]["url"])
```

Queued, running, merging, and settling are pending states. Wait at least five
seconds between manual checks and respect a longer Retry-After. Failed and
cancelled are terminal; HTTP 200 alone is not success. Deleted recordings are
reported explicitly. If lookup returns 404 after an uncertain submission,
replay the unchanged service job with the same ID. Stopping a caller or service
worker does not automatically cancel a paid server job.

The adapter has one total deadline across submission, retries, polling, and
download. Slow individual HTTP phases are bounded too. A timed-out request
worker can finish that one in-flight request, but cannot retry or start another
recording in the background. Retries preserve UUID and body, respect cooldowns
even after body-read errors, and never poll faster than five seconds.

The loaded adapter module admits at most eight HTTP workers without a task
queue. Normal calls can run concurrently within that bound. Full capacity or
any timed-out worker still finishing on the same client produces `client_busy`
before another request is sent. Retain the original request ID and recover when
capacity becomes available. Closing the adapter defers owned-client cleanup
until its active workers exit and never closes a caller-owned HTTP client.

API exceptions use local messages, not upstream error prose. Diagnostic code and
trace tokens are limited to 128 ASCII letters, digits, underscores or hyphens,
and values containing the configured API key are omitted. Signed URLs are not
included in these diagnostics; result URLs retained for recovery remain private.

Result metadata and the complete WAV container are validated before use:
24 kHz, mono, 16-bit PCM, complete chunks and nonempty aligned sample data.
Downloads are bounded and credential-free, including validated HTTPS redirects.
The internal `convert(text, voice_name, request_id=...)` method retains its
PCM result interface; `convert_multi(segments, request_id=...)` is used by the
service. Both now require a caller-known UUID. Unsupported legacy parameters
are rejected. `quota()` preserves the server's current `subscription` field.

## Offline Tests

From the repository root:

```bash
python -m pip install "httpx==0.28.1" "pytest==8.4.2" "pydantic==2.12.3"
python services/TTSService/test_flowspeech.py
python services/TTSService/verify_bundle.py
```

These tests use fake HTTP, extracted service methods, and no external service
credentials. The review bundle is checked and tested after extraction.
The separate `test_api.py` and repository-wide end-to-end scripts require live
services and are not part of these offline commands.
