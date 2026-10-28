# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""WO-FT-REVIEW-01 part 4: the app answers without keys, without Lightning and without Nightshift."""

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

from fasttrack import llm, sources
from fasttrack.agent import investigate
from fasttrack.memory import LocalStore

NO_KEYS = {k: "" for k in ("METERLESS_BASE_URL", "METERLESS_RUNTIME_TOKEN", "METERLESS_TOKEN", "NVIDIA_API_KEY", "FT_SAMPLE")}


class SampleModeTest(unittest.TestCase):
    def test_no_keys_means_sample_mode_with_routes(self):
        try:
            with mock.patch.dict(os.environ, NO_KEYS):
                mod = importlib.reload(llm)
                model = mod.open_llm()
            self.assertTrue(model.sample)
            with tempfile.TemporaryDirectory() as d:
                out = investigate("Knie, Köpenick", model, memory=LocalStore(Path(d) / "m.jsonl"))
        finally:
            importlib.reload(llm)
        self.assertTrue(out["sample_mode"])
        self.assertEqual(out["trace"]["source"], "local-sqlite")
        self.assertIsNone(out["trace"]["web"])
        self.assertEqual(len(out["routes"]), 3)
        self.assertTrue(all("SAMPLE" in r["route"] for r in out["routes"]))
        self.assertEqual(out["evidence"]["E1"]["row"]["practice_id"], "P01")
        self.assertIn("rule_id", out["evidence"]["E6"]["row"])
        self.assertTrue(all(c["provider"] == "sample" for c in out["model_calls"]))

    def test_ft_sample_wins_over_keys(self):
        with mock.patch.dict(os.environ, {"FT_SAMPLE": "1", "NVIDIA_API_KEY": "k"}):
            self.assertTrue(llm.open_llm().sample)


class JdbcFallbackTest(unittest.TestCase):
    def test_failed_connect_uses_local_sqlite(self):
        with mock.patch.dict(os.environ, {"ZETARIS_JDBC_JAR": "/nowhere/jdbc"}), \
                mock.patch.object(sources, "ZetarisSource", side_effect=RuntimeError("connection refused")):
            self.assertEqual(sources.open_source().name, "local-sqlite")


class NightshiftFallbackTest(unittest.TestCase):
    def run_with(self, nightshift):
        seen = []

        def nvidia(request):
            seen.append(request)
            return httpx.Response(200, json={"model": "nemotron", "choices": [{"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}]})

        env = {"METERLESS_BASE_URL": "http://ns:8088/v1", "METERLESS_RUNTIME_TOKEN": "t0k", "NVIDIA_API_KEY": "nv-k"}
        try:
            with mock.patch.dict(os.environ, env):
                mod = importlib.reload(llm)
                bot = mod.Nemotron()
                bot.http = httpx.Client(base_url=mod.BASE, transport=httpx.MockTransport(nightshift))
                bot.backup = httpx.Client(base_url=mod.NVIDIA_BASE, transport=httpx.MockTransport(nvidia))
                self.assertEqual(bot.json("sql", "s", "u"), {"ok": 1})
                return bot, seen, mod
        finally:
            importlib.reload(llm)

    def test_503_goes_to_the_nvidia_api(self):
        bot, seen, mod = self.run_with(lambda request: httpx.Response(503, json={"error": "admission_paused"}))
        self.assertEqual(len(bot.calls), 1)
        self.assertEqual(bot.calls[0]["provider"], "nvidia-api")
        self.assertEqual(bot.calls[0]["model"], mod._NVIDIA["sql"])
        self.assertEqual(seen[0].headers["authorization"], "Bearer nv-k")

    def test_connection_refused_goes_to_the_nvidia_api(self):
        def refused(request):
            raise httpx.ConnectError("refused", request=request)

        bot, seen, _ = self.run_with(refused)
        self.assertEqual([c["provider"] for c in bot.calls], ["nvidia-api"])

    def test_nightshift_answer_stays_on_nightshift(self):
        ok = lambda request: httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}]})
        bot, seen, _ = self.run_with(ok)
        self.assertEqual(seen, [])
        self.assertEqual(bot.calls[0]["provider"], "meterless-nightshift")


if __name__ == "__main__":
    unittest.main()
