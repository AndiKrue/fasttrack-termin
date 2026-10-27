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
            out = investigate("knee, Köpenick", FakeLLM(), LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
            self.assertEqual([r["route"] for r in out["routes"]], ["Open consultation"])  # uncited route dropped
            self.assertEqual(out["routes"][0]["evidence"], ["E1"])  # unknown id stripped
            self.assertIn("FT_WAITS.waits", out["evidence"]["E1"]["sql"])
            again = LocalStore(Path(d) / "m.jsonl").recall("knee Köpenick")
            self.assertEqual(again[0]["route"], "Open consultation")

    def test_dropped_route_is_explained(self):
        class Strict(FakeLLM):
            def json(self, role, system, user, max_tokens=2048):
                if role == "verifier":
                    return {"keep": [0], "notes": ["Invented: no row supports it"]}
                return super().json(role, system, user, max_tokens)

        with tempfile.TemporaryDirectory() as d:
            out = investigate("knee, Köpenick", Strict(), LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
        self.assertEqual([x["route"] for x in out["dropped"]], ["Invented"])
        self.assertEqual(out["dropped"][0]["note"], "Invented: no row supports it")
        self.assertEqual(out["dropped"][0]["reason"], "no cited evidence row exists")
        self.assertEqual(out["routes"][0]["why_trace"][0]["eid"], "E1")

    def test_sql_guard(self):
        for bad in ["DROP TABLE x", "SELECT 1; DELETE FROM x", "ATTACH DATABASE 'x' AS y", "update x set a=1"]:
            with self.assertRaises(ValueError):
                check_sql(bad)
        self.assertEqual(LocalSource().query("SELECT count(*) AS n FROM FT_RULES.rules")[0]["n"], 7)

    def test_parse_json_skips_reasoning(self):
        self.assertEqual(parse_json('<think>{"no":1}</think> ok {"a": [1]}'), {"a": [1]})


if __name__ == "__main__":
    unittest.main()


class WebEvidenceTests(unittest.TestCase):
    def test_rows_keep_only_real_page_urls_and_skip_booking_portals(self):
        from fasttrack.web import FirecrawlSearch, web_evidence

        class LLM:
            def json(self, role, system, user, max_tokens=2048):
                if "search query" in system:
                    return {"query": "Orthopäde Köpenick offene Sprechstunde"}
                return {"practices": [{"name": "A", "url": "https://praxis-a.example/"}, {"name": "Ghost", "url": "https://nowhere.example/"}]}

        search = FirecrawlSearch(key="test")
        search.http = None
        search.search = lambda q, limit=5: [{"url": "https://praxis-a.example/", "title": "A", "text": "Offene Sprechstunde Mo 8-10"}]
        query, rows = web_evidence("knee Köpenick", LLM(), search)
        self.assertEqual([r["name"] for r in rows], ["A"])
        self.assertIn("Köpenick", query)


class ParallelTests(unittest.TestCase):
    def test_sql_drafts_run_concurrently(self):
        import time

        class Slow(FakeLLM):
            def json(self, role, system, user, max_tokens=2048):
                if role == "sql":
                    time.sleep(0.3)
                return super().json(role, system, user, max_tokens)

        with tempfile.TemporaryDirectory() as d:
            started = time.monotonic()
            investigate("knee, Köpenick", Slow(), LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
            self.assertLess(time.monotonic() - started, 0.55)  # two 0.3 s drafts overlap
