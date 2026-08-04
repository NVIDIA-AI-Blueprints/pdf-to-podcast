import base64
import unittest

import httpx

from services.TTSService.flowspeech import (
    FlowSpeechClient,
    FlowSpeechError,
    pcm_to_wav,
)


class FlowSpeechClientTest(unittest.TestCase):
    def test_convert_sends_bearer_request_and_decodes_pcm(self):
        pcm = b"\x01\x02\x03\x04"

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                request.url,
                "https://flowspeech.io/api/ai/text-to-speech",
            )
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            self.assertIn(b'"voiceName":"Kore"', request.content)
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "message": "ok",
                    "data": {
                        "audioBase64": base64.b64encode(pcm).decode(),
                        "mimeType": "audio/L16;rate=24000",
                        "sampleRate": 24000,
                        "numChannels": 1,
                        "bitsPerSample": 16,
                    },
                },
            )

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        client = FlowSpeechClient("test-key", httpx_client=http_client)

        audio = client.convert("Hello from FlowSpeech", "Kore")

        self.assertEqual(audio.pcm, pcm)
        self.assertEqual(audio.sample_rate, 24000)
        wav = pcm_to_wav(audio)
        self.assertEqual(wav[:4], b"RIFF")
        self.assertEqual(wav[8:12], b"WAVE")

    def test_convert_rejects_api_error(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                401,
                json={"code": 401, "message": "Invalid API key"},
            )
        )
        client = FlowSpeechClient(
            "test-key",
            httpx_client=httpx.Client(transport=transport),
        )

        with self.assertRaisesRegex(FlowSpeechError, "Invalid API key"):
            client.convert("Hello", "Kore")


if __name__ == "__main__":
    unittest.main()
