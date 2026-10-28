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
        self.assertEqual(body, {"maps": False})

    def test_key_is_returned_but_never_logged(self):
        body, log = self.get_config({"GOOGLE_MAPS_EMBED_KEY": "test-embed-key-123"})
        self.assertEqual(body, {"maps": True, "embed_key": "test-embed-key-123"})
        self.assertIn("/config", log)  # the request was logged ...
        self.assertNotIn("test-embed-key-123", log)  # ... without the key


class StreamKeepaliveTest(unittest.TestCase):
    def test_blank_lines_keep_a_slow_stream_alive(self):
        def slow(question, llm, on_step):
            on_step({"step": "plan"})
            threading.Event().wait(0.35)  # a silent model call
            return {"routes": []}

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with mock.patch("fasttrack.app.KEEPALIVE_S", 0.1), mock.patch("fasttrack.app.investigate", slow), \
                    contextlib.redirect_stderr(io.StringIO()):
                req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/ask/stream",
                                             data=json.dumps({"question": "q"}).encode(), method="POST",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req) as r:
                    lines = r.read().decode().split("\n")
        finally:
            server.shutdown()
            server.server_close()
        self.assertGreaterEqual(lines.count(""), 3)  # keepalives (plus the final newline)
        payload = [json.loads(x) for x in lines if x.strip()]
        self.assertEqual(payload, [{"step": {"step": "plan"}}, {"result": {"routes": []}}])


if __name__ == "__main__":
    unittest.main()
