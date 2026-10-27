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

        env = {"METERLESS_BASE_URL": "http://host.docker.internal:8088", "METERLESS_TOKEN": "t0k"}
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
