# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
import contextlib
import io
import json
import os
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from fasttrack.app import Handler


class ConfigTest(unittest.TestCase):
    def get_config(self, env):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        log = io.StringIO()
        try:
            with mock.patch.dict(os.environ, env, clear=False), contextlib.redirect_stderr(log):
                with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/config") as r:
                    body = json.loads(r.read())
        finally:
            server.shutdown()
            server.server_close()
        return body, log.getvalue()

    def test_no_key_means_no_maps(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_MAPS_EMBED_KEY", None)
            body, _ = self.get_config({})
        self.assertEqual(body["maps"], False)

    def test_key_is_returned_but_never_logged(self):
        body, log = self.get_config({"GOOGLE_MAPS_EMBED_KEY": "test-embed-key-123"})
        self.assertEqual((body["maps"], body["embed_key"]), (True, "test-embed-key-123"))
        self.assertIn("/config", log)  # the request was logged ...
        self.assertNotIn("test-embed-key-123", log)  # ... without the key


if __name__ == "__main__":
    unittest.main()


class SpeechEndpointTest(unittest.TestCase):
    class FakeLLM:
        def transcribe(self, audio, mime, lang=None):
            return "knee pain in Köpenick"

        def speak(self, text, voice=None):
            return b"ID3mp3"

    def post(self, path, body: bytes, ctype: str, env=None, length=None):
        import http.client

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = {"METERLESS_BASE_URL": "http://nightshift:8088/v1"} if env is None else env
        log = io.StringIO()
        try:
            with mock.patch.dict(os.environ, env), mock.patch.object(Handler, "llm", self.FakeLLM()), contextlib.redirect_stderr(log):
                if not env:
                    os.environ.pop("METERLESS_BASE_URL", None)
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
                conn.putrequest("POST", path)
                conn.putheader("Content-Type", ctype)
                conn.putheader("Content-Length", str(length if length is not None else len(body)))
                conn.endheaders()
                conn.send(body)
                r = conn.getresponse()
                out = (r.status, r.getheader("Content-Type"), r.read())
                conn.close()
        finally:
            server.shutdown()
            server.server_close()
        return out, log.getvalue()

    @staticmethod
    def wav(seconds: float) -> bytes:
        rate = 32000  # bytes per second: 16 kHz, 16-bit mono
        n = int(rate * seconds)
        return b"RIFF" + (36 + n).to_bytes(4, "little") + b"WAVEfmt " + bytes(12) + rate.to_bytes(4, "little") + bytes(8) + n.to_bytes(4, "little") + bytes(n)

    def test_stt_returns_text_and_logs_neither_audio_nor_text(self):
        (status, _, body), log = self.post("/stt", self.wav(1), "audio/wav")
        self.assertEqual((status, json.loads(body)), (200, {"text": "knee pain in Köpenick"}))
        self.assertNotIn("knee", log)

    def test_stt_rejects_wrong_type_large_and_long_audio(self):
        self.assertEqual(self.post("/stt", b"{}", "application/json")[0][0], 415)
        self.assertEqual(self.post("/stt", b"x", "audio/webm", length=3 * 1024 * 1024)[0][0], 413)
        self.assertEqual(self.post("/stt", self.wav(61), "audio/wav")[0][0], 413)

    def test_stt_and_tts_need_nightshift(self):
        self.assertEqual(self.post("/stt", self.wav(1), "audio/wav", env={})[0][0], 503)
        self.assertEqual(self.post("/tts", b'{"text": "hi"}', "application/json", env={})[0][0], 503)

    def test_tts_returns_mp3_and_checks_text(self):
        (status, ctype, body), _ = self.post("/tts", json.dumps({"text": "About 3 days."}).encode(), "application/json")
        self.assertEqual((status, ctype, body), (200, "audio/mpeg", b"ID3mp3"))
        self.assertEqual(self.post("/tts", b'{"text": " "}', "application/json")[0][0], 400)
        self.assertEqual(self.post("/tts", json.dumps({"text": "a" * 1501}).encode(), "application/json")[0][0], 413)

    def test_unserved_speech_is_503(self):
        class Down(self.FakeLLM):
            def speak(self, text, voice=None):
                raise RuntimeError("speech output is not available on Meterless Nightshift right now")

        with mock.patch.object(self, "FakeLLM", Down):
            self.assertEqual(self.post("/tts", b'{"text": "hi"}', "application/json")[0][0], 503)
