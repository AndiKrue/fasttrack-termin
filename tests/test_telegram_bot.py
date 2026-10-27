# SPDX-License-Identifier: AGPL-3.0-or-later
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from fasttrack.telegram_bot import Bot, Telegram, render

TOKEN = "123456:SECRET-token-value"


class FakeResponse:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data


class FakeClient:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def post(self, url, json):
        method = url.rsplit("/", 1)[1]
        self.calls.append((method, json))
        if self.fail == method:
            return FakeResponse({"ok": False, "description": f"bad request for {url}"}, 400)
        if method == "sendMessage":
            return FakeResponse({"ok": True, "result": {"message_id": len(self.calls)}})
        return FakeResponse({"ok": True, "result": True})


def fake_ask(question, llm, on_step=None):
    on_step({"step": "plan", "questions": ["a", "b"]})
    on_step({"step": "query", "queries": [{"evidence": ["E1"]}]})
    on_step({"step": "verify", "kept": 1, "dropped": 0})
    return {
        "routes": [{"route": "Open consultation <b>", "expected_days": 0, "why": "R4 & P01", "evidence": ["E1"]}],
        "evidence": {"E1": {"url": "https://praxis.example/", "row": {"name": "Praxis A", "phone": "+49 30 123", "address": "Bahnhofstr. 1, Berlin"}}},
        "caveats": [],
    }


class BotTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.bot = Bot(Telegram(TOKEN, self.client), llm=None, ask=fake_ask)

    def test_start_offers_miniapp_button(self):
        with mock.patch.dict(os.environ, {"FT_MINIAPP_URL": "https://x.trycloudflare.com/miniapp"}):
            self.bot.handle({"message": {"text": "/start", "chat": {"id": 7}}})
        method, params = self.client.calls[0]
        self.assertEqual(method, "sendMessage")
        button = params["reply_markup"]["inline_keyboard"][0][0]
        self.assertEqual(button["web_app"]["url"], "https://x.trycloudflare.com/miniapp")

    def test_question_edits_status_and_answers_escaped_with_route(self):
        self.bot.handle({"message": {"text": "knee Köpenick", "chat": {"id": 7}}}).join(5)
        methods = [m for m, _ in self.client.calls]
        self.assertEqual(methods.count("editMessageText"), 3)
        final = self.client.calls[-1][1]["text"]
        self.assertIn("Open consultation &lt;b&gt;", final)
        self.assertIn("R4 &amp; P01", final)
        self.assertIn("https://www.openstreetmap.org/directions?to=Bahnhofstr.%201%2C%20Berlin", final)
        self.assertIn("+49 30 123", final)
        self.assertNotIn(7, self.bot.busy)

    def test_token_never_in_errors_or_logs(self):
        bot = Bot(Telegram(TOKEN, FakeClient(fail="sendMessage")), llm=None, ask=fake_ask)
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(RuntimeError) as caught:
            bot.tg.call("sendMessage", chat_id=1, text="x")
        self.assertNotIn(TOKEN, str(caught.exception))
        with redirect_stdout(out):
            bot.handle({"message": {"text": "q", "chat": {"id": 1}}}).join(5)
        self.assertNotIn(TOKEN, out.getvalue())

    def test_render_splits_long_answers(self):
        long = {"routes": [{"route": "r", "why": "x" * 3000, "evidence": []} for _ in range(3)], "evidence": {}}
        self.assertTrue(all(len(m) <= 4096 for m in render(long)))
        self.assertGreater(len(render(long)), 1)


if __name__ == "__main__":
    unittest.main()
