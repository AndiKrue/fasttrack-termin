# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
import os
import unittest
from unittest import mock

from fasttrack import telegram_bot
from fasttrack.env import load_env


class EnvTest(unittest.TestCase):
    def test_env_file_fills_missing_and_keeps_existing(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".env"
            f.write_text('# c\nFT_A=one\nexport FT_B="two"\nFT_C=file\nnoequals\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {"FT_C": "shell"}, clear=False):
                load_env(f)
                self.assertEqual((os.environ["FT_A"], os.environ["FT_B"], os.environ["FT_C"]), ("one", "two", "shell"))

    def test_miniapp_url_from_tunnel_metrics(self):
        resp = mock.Mock()
        resp.json.return_value = {"hostname": "abc-def.trycloudflare.com"}
        with mock.patch.dict(os.environ, {"FT_TUNNEL_METRICS": "http://tunnel:20241"}), mock.patch.object(telegram_bot.httpx, "get", return_value=resp):
            os.environ.pop("FT_MINIAPP_URL", None)
            self.assertEqual(telegram_bot.miniapp_url(), "https://abc-def.trycloudflare.com/miniapp")


if __name__ == "__main__":
    unittest.main()
