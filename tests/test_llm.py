# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
import unittest
from unittest import mock

from fasttrack import llm


class FallbackTest(unittest.TestCase):
    def test_ultra_answers_after_two_lightning_misses(self):
        bot = llm.Nemotron.__new__(llm.Nemotron)
        bot.last_finish = "length"
        seen = []

        def chat(role, system, user, max_tokens=2048, model=None, think=None):
            seen.append(model)
            return '{"sql": "SELECT 1"}' if model == llm.FALLBACK else "still thinking"

        with mock.patch.object(bot, "chat", side_effect=chat):
            self.assertEqual(bot.json("sql", "s", "u"), {"sql": "SELECT 1"})
        self.assertEqual(seen, [None, None, llm.FALLBACK])


if __name__ == "__main__":
    unittest.main()


class NightshiftTest(unittest.TestCase):
    def test_nightshift_is_primary_when_configured(self):
        import importlib
        import os

        import httpx

        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["headers"] = request.headers
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}]})

        env = {"METERLESS_BASE_URL": "http://host.docker.internal:8088", "METERLESS_RUNTIME_TOKEN": "t0k"}
        try:
            with mock.patch.dict(os.environ, env):
                mod = importlib.reload(llm)
                bot = mod.Nemotron()
                bot.http = httpx.Client(base_url=mod.BASE, transport=httpx.MockTransport(handler))
                self.assertEqual(bot.json("sql", "s", "u"), {"ok": 1})
            self.assertEqual(seen["url"], "http://host.docker.internal:8088/v1/chat/completions")
            self.assertEqual(seen["headers"]["meterless-app"], "fasttrack-termin")
            self.assertEqual(seen["headers"]["authorization"], "Bearer t0k")
            self.assertEqual(bot.calls[0]["provider"], "meterless-nightshift")
            self.assertEqual(bot.calls[0]["model"], "meterless/auto")
        finally:
            importlib.reload(llm)

    def test_placeholder_token_is_refused(self):
        import importlib
        import os

        try:
            with mock.patch.dict(os.environ, {"METERLESS_BASE_URL": "http://127.0.0.1:8088/v1", "METERLESS_TOKEN": "rt-local"}):
                mod = importlib.reload(llm)
                with self.assertRaises(RuntimeError):
                    mod.Nemotron()
        finally:
            importlib.reload(llm)


class SpeechTest(unittest.TestCase):
    def nightshift(self, handler):
        import importlib
        import os

        import httpx

        env = {"METERLESS_BASE_URL": "http://host.docker.internal:8088/v1", "METERLESS_RUNTIME_TOKEN": "t0k"}
        with mock.patch.dict(os.environ, env):
            mod = importlib.reload(llm)
            bot = mod.Nemotron()
        bot.http = httpx.Client(base_url=mod.BASE, transport=httpx.MockTransport(handler))
        self.addCleanup(importlib.reload, llm)
        return bot

    def test_transcribe_posts_base64_audio_to_nightshift(self):
        import base64
        import json

        import httpx

        seen = {}

        def handler(request):
            seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
            return httpx.Response(200, json={"text": " knee pain ", "source": "voice-asr-engine"})

        bot = self.nightshift(handler)
        self.assertEqual(bot.transcribe(b"RIFFwav", "audio/wav", "de"), "knee pain")
        self.assertEqual(seen["url"], "http://host.docker.internal:8088/v1/meterless/transcribe")
        self.assertEqual(seen["headers"]["meterless-app"], "fasttrack-termin")
        self.assertEqual(base64.b64decode(seen["body"]["audio_base64"]), b"RIFFwav")
        self.assertEqual((seen["body"]["filename"], seen["body"]["model"], seen["body"]["language"]), ("speech.wav", "meterless/transcribe", "de"))
        self.assertEqual(bot.calls[-1]["role"], "stt")

    def test_speak_returns_audio_and_logs_the_call(self):
        import json

        import httpx

        seen = {}

        def handler(request):
            seen["url"], seen["body"] = str(request.url), json.loads(request.content)
            return httpx.Response(200, content=b"ID3mp3", headers={"content-type": "audio/mpeg"})

        bot = self.nightshift(handler)
        self.assertEqual(bot.speak("About 3 days."), b"ID3mp3")
        self.assertEqual(seen["url"], "http://host.docker.internal:8088/v1/audio/speech")
        self.assertEqual(seen["body"], {"model": "meterless/speech", "input": "About 3 days.", "response_format": "mp3"})
        self.assertEqual(bot.calls[-1]["role"], "tts")

    def test_unserved_speech_route_is_a_clear_runtime_error(self):
        import httpx

        bot = self.nightshift(lambda request: httpx.Response(404, json={"error": {"message": "not_found"}}))
        with self.assertRaises(RuntimeError):
            bot.speak("x")

    def test_without_nightshift_speech_is_refused(self):
        bot = llm.Nemotron.__new__(llm.Nemotron)
        with mock.patch.object(llm, "NIGHTSHIFT", ""):
            with self.assertRaises(RuntimeError):
                bot.transcribe(b"x", "audio/wav")
            with self.assertRaises(RuntimeError):
                bot.speak("x")
