# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import tempfile
import unittest
from pathlib import Path

from fasttrack.agent import investigate
from fasttrack.llm import parse_json
from fasttrack.memory import LocalStore
from fasttrack.sources import LocalSource, check_sql


class FakeLLM:
    calls = []

    def json(self, role, system, user, max_tokens=2048):
        if role == "planner":
            return {"questions": ["open consultation orthopaedics in Treptow-Köpenick", "rules"]}
        if role == "sql":
            if "rules" in user:
                return {"sql": "SELECT rule_id, rule FROM FT_RULES.rules WHERE topic = 'open consultation'"}
            return {"sql": "SELECT p.name, w.channel, w.days_to_appointment FROM FT_PRACTICES.practices p JOIN FT_WAITS.waits w ON p.practice_id = w.practice_id WHERE p.specialty = 'orthopaedics' AND p.district = 'Treptow-Köpenick'"}
        if role == "answer":
            return {"routes": [{"route": "Open consultation", "expected_days": 0, "why": "x", "evidence": ["E1", "E9"]},
                               {"route": "Invented", "expected_days": 1, "why": "y", "evidence": ["E99"]}], "caveats": ["sample data"]}
        return {"keep": [0, 1]}


class AgentTests(unittest.TestCase):
    def test_federated_join_and_citations(self):
        with tempfile.TemporaryDirectory() as d:
            out = investigate("knee, Köpenick", FakeLLM(), LocalSource(), LocalStore(Path(d) / "m.jsonl"))
            self.assertEqual([r["route"] for r in out["routes"]], ["Open consultation"])  # uncited route dropped
            self.assertEqual(out["routes"][0]["evidence"], ["E1"])  # unknown id stripped
            self.assertIn("FT_WAITS.waits", out["evidence"]["E1"]["sql"])
            again = LocalStore(Path(d) / "m.jsonl").recall("knee Köpenick")
            self.assertEqual(again[0]["route"], "Open consultation")

    def test_sql_guard(self):
        for bad in ["DROP TABLE x", "SELECT 1; DELETE FROM x", "ATTACH DATABASE 'x' AS y", "update x set a=1"]:
            with self.assertRaises(ValueError):
                check_sql(bad)
        self.assertEqual(LocalSource().query("SELECT count(*) AS n FROM FT_RULES.rules")[0]["n"], 7)

    def test_parse_json_skips_reasoning(self):
        self.assertEqual(parse_json('<think>{"no":1}</think> ok {"a": [1]}'), {"a": [1]})


if __name__ == "__main__":
    unittest.main()
