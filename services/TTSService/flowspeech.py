import io
import wave
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

if __package__:
    from .flowspeech_v1 import ApiError, V1Client, make_input
else:
    from flowspeech_v1 import ApiError, V1Client, make_input


@dataclass(frozen=True)
class FlowSpeechAudio:
    pcm: bytes
    sample_rate: int
    channels: int
    bits_per_sample: int
    job_id: str | None = None
    request_id: str | None = None


FlowSpeechError = ApiError


def request_id_for_job(job_id: str) -> str:
    """Stable across worker restarts; changed input must use a new service job ID."""
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("job_id must be a nonempty string")
    return str(uuid5(NAMESPACE_URL, "pdf-to-podcast/flowspeech/v1/" + job_id))


def dialogue_segments(dialogue, voice_mapping):
    if not isinstance(voice_mapping, dict) or not voice_mapping:
        raise ValueError("voice_mapping must be a nonempty object")
    segments = []
    for entry in dialogue:
        voice = (
            entry.voice_id
            if entry.voice_id is not None
            else voice_mapping.get(entry.speaker)
        )
        segments.append(
            {"speaker": entry.speaker, "text": entry.text, "voiceName": voice}
        )
    return make_input(segments=segments)["segments"]


class FlowSpeechClient(V1Client):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://flowspeech.io",
        httpx_client=None,
        **options,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx_client,
            user_agent="pdf-to-podcast/flowspeech-v1",
            **options,
        )

    def convert(
        self, text: str, voice_name: str, *, request_id: str
    ) -> FlowSpeechAudio:
        return self._convert(make_input(text, voice_name), request_id)

    def convert_multi(self, segments, *, request_id: str) -> FlowSpeechAudio:
        return self._convert(make_input(segments=segments), request_id)

    def _convert(self, speech_input, request_id):
        job, wav, request_id = self.generate(speech_input, request_id=request_id)
        # generate() validates the entire RIFF container before this compatibility decode.
        with wave.open(io.BytesIO(wav), "rb") as audio:
            pcm = audio.readframes(audio.getnframes())
        return FlowSpeechAudio(pcm, 24000, 1, 16, job["id"], request_id)


def pcm_to_wav(audio: FlowSpeechAudio) -> bytes:
    if (
        (audio.sample_rate, audio.channels, audio.bits_per_sample) != (24000, 1, 16)
        or not isinstance(audio.pcm, bytes)
        or not audio.pcm
        or len(audio.pcm) % 2
    ):
        raise FlowSpeechError("Expected nonempty aligned 24 kHz mono 16-bit PCM")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(audio.channels)
        wav_file.setsampwidth(audio.bits_per_sample // 8)
        wav_file.setframerate(audio.sample_rate)
        wav_file.writeframes(audio.pcm)
    return output.getvalue()
