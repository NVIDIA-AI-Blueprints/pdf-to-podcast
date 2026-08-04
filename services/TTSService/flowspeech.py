import base64
import binascii
import io
import wave
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class FlowSpeechAudio:
    pcm: bytes
    sample_rate: int
    channels: int
    bits_per_sample: int


class FlowSpeechError(RuntimeError):
    """Raised when FlowSpeech returns an invalid or unsuccessful response."""


class FlowSpeechClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://flowspeech.io",
        httpx_client: httpx.Client | None = None,
    ):
        if not api_key:
            raise FlowSpeechError(
                "FLOWSPEECH_API_KEY is required when TTS_PROVIDER=flowspeech"
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.httpx_client = httpx_client or httpx.Client(timeout=120)
        self._owns_client = httpx_client is None

    def close(self):
        if self._owns_client:
            self.httpx_client.close()

    def convert(self, text: str, voice_name: str) -> FlowSpeechAudio:
        response = self.httpx_client.post(
            f"{self.base_url}/api/ai/text-to-speech",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "nvidia-pdf-to-podcast/flowspeech",
            },
            json={
                "text": text,
                "originalText": text,
                "speakers": [{"voiceName": voice_name}],
            },
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise FlowSpeechError("FlowSpeech returned a non-JSON response") from exc

        if response.status_code >= 400:
            message = payload.get("message") if isinstance(payload, dict) else None
            raise FlowSpeechError(
                message or f"FlowSpeech returned HTTP {response.status_code}"
            )
        if not isinstance(payload, dict) or payload.get("code") != 0:
            message = payload.get("message") if isinstance(payload, dict) else None
            raise FlowSpeechError(message or "FlowSpeech returned an error")

        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("audioBase64"):
            raise FlowSpeechError("FlowSpeech response did not include audioBase64")

        try:
            pcm = base64.b64decode(data["audioBase64"], validate=True)
        except (TypeError, ValueError, binascii.Error) as exc:
            raise FlowSpeechError("FlowSpeech returned invalid base64 audio") from exc

        audio = FlowSpeechAudio(
            pcm=pcm,
            sample_rate=int(data.get("sampleRate") or 24000),
            channels=int(data.get("numChannels") or 1),
            bits_per_sample=int(data.get("bitsPerSample") or 16),
        )
        if (audio.sample_rate, audio.channels, audio.bits_per_sample) != (
            24000,
            1,
            16,
        ):
            raise FlowSpeechError(
                "FlowSpeech returned an unsupported PCM format; expected "
                "24 kHz, mono, 16-bit audio"
            )
        return audio


def pcm_to_wav(audio: FlowSpeechAudio) -> bytes:
    if audio.bits_per_sample % 8 != 0:
        raise FlowSpeechError("FlowSpeech returned an unsupported PCM bit depth")

    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(audio.channels)
        wav_file.setsampwidth(audio.bits_per_sample // 8)
        wav_file.setframerate(audio.sample_rate)
        wav_file.writeframes(audio.pcm)
    return output.getvalue()
