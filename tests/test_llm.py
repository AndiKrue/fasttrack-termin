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

        def chat(role, system, user, max_tokens=2048, model=None):
            seen.append(model)
            return '{"sql": "SELECT 1"}' if model == llm.FALLBACK else "still thinking"

        with mock.patch.object(bot, "chat", side_effect=chat):
            self.assertEqual(bot.json("sql", "s", "u"), {"sql": "SELECT 1"})
        self.assertEqual(seen, [None, None, llm.FALLBACK])


if __name__ == "__main__":
    unittest.main()
