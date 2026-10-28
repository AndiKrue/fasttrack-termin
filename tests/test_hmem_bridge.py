# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""WO-FT-REVIEW-01 part 5: the H-MEM bridge itself, and memory that cannot fail an answer."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fasttrack.agent import investigate
from fasttrack.memory import HMemStore
from fasttrack.sources import LocalSource
from tests.test_agent import FakeLLM


def bridge():
    try:
        return HMemStore()
    except FileNotFoundError:
        return None


@unittest.skipIf(bridge() is None, "H-MEM bridge needs Node and tsx (npm install in meterless/)")
class BridgeTest(unittest.TestCase):
    def test_umlaut_and_spelled_out_umlaut_meet(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"FT_HMEM_DIR": d}):
            store = bridge()
            store.remember({
                "run_id": "t1",
                "question": "Ich wohne in Köpenick und suche einen Orthopäden für mein Knie",
                "route": "Offene Sprechstunde, Orthopädie Köpenick",
                "why": "0 Tage laut Beispieldaten",
            })
            found = store.recall("Knie Koepenick Orthopäde")
            umlaut_only = store.recall("Koepenick")  # no other shared word: only the umlaut spelling can match
        self.assertEqual([r["source"] for r in found], ["fasttrack:t1"])
        self.assertEqual([r["source"] for r in umlaut_only], ["fasttrack:t1"])
        self.assertIn("koepenick", found[0]["content"])


class BrokenMemory:
    name = "broken"

    def recall(self, query, limit=5):
        raise RuntimeError("H-MEM bridge failed: tsx exited")

    def remember(self, record):
        raise RuntimeError("H-MEM bridge failed: disk full")


class GuardTest(unittest.TestCase):
    def test_memory_failure_never_fails_the_answer(self):
        out = investigate("knee, Köpenick", FakeLLM(), LocalSource(), BrokenMemory(), search=False)
        self.assertEqual([r["route"] for r in out["routes"]], ["Open consultation"])
        steps = {s["step"]: s for s in out["trace"]["steps"]}
        self.assertIn("tsx exited", steps["recall"]["error"])
        self.assertIn("disk full", steps["remember"]["error"])


if __name__ == "__main__":
    unittest.main()
