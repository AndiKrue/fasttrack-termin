# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""DRAFT WO-FT-ASK-01: /ask protection, off by default."""

import hashlib
import hmac
import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.parse import urlencode

from fasttrack.app import Handler
from fasttrack.auth import allowed, telegram_ok

TOKEN = "123:test-token"


def init_data(token=TOKEN, auth_date=None, **extra):
    fields = {"auth_date": str(int(auth_date or time.time())), "query_id": "q1", "user": '{"id":1}', **extra}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class TelegramCheckTest(unittest.TestCase):
    def test_signed_by_our_bot(self):
        self.assertTrue(telegram_ok(init_data(), TOKEN))

    def test_other_bot_tampered_or_stale_is_refused(self):
        self.assertFalse(telegram_ok(init_data(token="999:other"), TOKEN))
        self.assertFalse(telegram_ok(init_data().replace("q1", "q2"), TOKEN))
        self.assertFalse(telegram_ok(init_data(auth_date=time.time() - 2 * 86400), TOKEN))
        self.assertFalse(telegram_ok("", TOKEN))


class AllowedTest(unittest.TestCase):
    def test_off_by_default(self):
        with mock.patch.dict(os.environ, {"FT_ASK_AUTH": ""}):
            self.assertTrue(allowed({}))

    def test_on_needs_init_data_or_key(self):
        env = {"FT_ASK_AUTH": "on", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_BOT_TOKEN_TEST": TOKEN, "FT_ASK_SECRET": "s3cret"}
        with mock.patch.dict(os.environ, env):
            self.assertFalse(allowed({}))
            self.assertTrue(allowed({"X-Telegram-Init-Data": init_data()}))
            self.assertTrue(allowed({"X-FT-Key": "s3cret"}))
            self.assertFalse(allowed({"X-FT-Key": "guess"}))

    def test_on_without_secret_never_accepts_an_empty_key(self):
        with mock.patch.dict(os.environ, {"FT_ASK_AUTH": "on", "FT_ASK_SECRET": "", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_BOT_TOKEN_TEST": ""}):
            self.assertFalse(allowed({"X-FT-Key": ""}))


class EndpointTest(unittest.TestCase):
    def test_ask_is_refused_before_the_agent_runs(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with mock.patch.dict(os.environ, {"FT_ASK_AUTH": "on", "FT_ASK_SECRET": "s3cret"}), \
                    mock.patch("fasttrack.app.investigate", side_effect=AssertionError("agent ran")):
                for path in ("/ask", "/ask/stream"):
                    req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}{path}", data=b'{"question": "x"}', method="POST")
                    with self.assertRaises(urllib.error.HTTPError) as cm:
                        urllib.request.urlopen(req)
                    self.assertEqual(cm.exception.code, 401)
                    self.assertIn("mini app", json.loads(cm.exception.read())["error"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
