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

    def json(self, role, system, user, max_tokens=2048, think=None):
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
            def json(self, role, system, user, max_tokens=2048, think=None):
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
        nested = '{"routes": [{"route": "A", "evidence": ["E1"]}], "caveats": ["c"]}'
        self.assertEqual(parse_json(nested)["routes"][0]["route"], "A")


if __name__ == "__main__":
    unittest.main()


class WebEvidenceTests(unittest.TestCase):
    def test_rows_keep_only_real_page_urls_and_skip_booking_portals(self):
        from fasttrack.web import FirecrawlSearch, web_evidence

        class LLM:
            def json(self, role, system, user, max_tokens=2048, think=None):
                if "search query" in system:
                    return {"query": "Orthopäde Köpenick offene Sprechstunde"}
                return {"practices": [{"name": "A", "url": "https://praxis-a.example/"}, {"name": "Ghost", "url": "https://nowhere.example/"}]}

        search = FirecrawlSearch(key="test")
        search.http = None
        search.search = lambda q, limit=5: [{"url": "https://praxis-a.example/", "title": "A", "text": "Offene Sprechstunde Mo 8-10"}]
        query, rows = web_evidence("knee Köpenick", LLM(), search)
        self.assertEqual([r["name"] for r in rows], ["A"])
        self.assertIn("Köpenick", query)

    def test_private_and_self_pay_practices_are_dropped(self):
        from fasttrack.web import statutory_ok
        self.assertFalse(statutory_ok({"name": "Privatpraxis Orthopädie Berlin – Dr. med. K. Stein"}))
        self.assertFalse(statutory_ok({"name": "Praxis Nord", "insurance": "Privatpatienten und Selbstzahler"}))
        self.assertTrue(statutory_ok({"name": "Praxis Süd", "insurance": "alle Kassen und privat"}))
        self.assertTrue(statutory_ok({"name": "Orthopädie am Markt", "insurance": None}))

    def test_extraction_reads_at_most_three_pages_of_3000_chars(self):
        from fasttrack import web

        seen = []

        class LLM:
            def json(self, role, system, user, max_tokens=2048, think=None):
                if "search query" in system:
                    return {"query": "Hautarzt Berlin"}
                seen.append(user)
                return {"practices": []}

        class Search:
            def search(self, q, limit=5):
                return [{"url": f"https://p{i}.example/", "title": "", "text": "z" * 5000} for i in range(5)]

        web.web_evidence("skin", LLM(), Search())
        self.assertEqual(len(seen), 3)
        self.assertTrue(all(u.count("z") == 3000 for u in seen))

    def test_slow_page_is_dropped_and_finished_pages_are_kept(self):
        import time
        from unittest import mock

        from fasttrack import web

        class LLM:
            def json(self, role, system, user, max_tokens=2048, think=None):
                if "search query" in system:
                    return {"query": "Hautarzt Berlin"}
                url = "https://slow.example/" if "slow.example" in user else "https://fast.example/"
                if "slow" in url:
                    time.sleep(1)
                return {"practices": [{"name": url, "url": url}]}

        class Search:
            def search(self, q, limit=5):
                return [{"url": u, "title": "", "text": ""} for u in ("https://fast.example/", "https://slow.example/")]

        with mock.patch.object(web, "EXTRACT_SECONDS", 0.3):
            started = time.monotonic()
            _, rows = web.web_evidence("skin", LLM(), Search())
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertEqual([r["url"] for r in rows], ["https://fast.example/"])


class ModelCallsTests(unittest.TestCase):
    def test_each_run_reports_only_its_own_calls(self):
        class Counting(FakeLLM):
            def __init__(self):
                self.calls = []

            def json(self, role, system, user, max_tokens=2048, think=None):
                self.calls.append({"role": role})
                return super().json(role, system, user, max_tokens)

        llm = Counting()
        with tempfile.TemporaryDirectory() as d:
            first = investigate("knee, Köpenick", llm, LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
            second = investigate("knee, Köpenick", llm, LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
        self.assertGreater(len(first["model_calls"]), 0)
        self.assertEqual(len(second["model_calls"]), len(first["model_calls"]))
        self.assertEqual(len(llm.calls), 2 * len(first["model_calls"]))


class ParallelTests(unittest.TestCase):
    def test_sql_drafts_run_concurrently(self):
        import time

        class Slow(FakeLLM):
            def json(self, role, system, user, max_tokens=2048, think=None):
                if role == "sql":
                    time.sleep(0.3)
                return super().json(role, system, user, max_tokens)

        with tempfile.TemporaryDirectory() as d:
            started = time.monotonic()
            investigate("knee, Köpenick", Slow(), LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
            self.assertLess(time.monotonic() - started, 0.55)  # two 0.3 s drafts overlap


class SpecialtyTests(unittest.TestCase):
    """A cardiology question must never be answered with dermatology waiting data."""

    class Cardio:
        def __init__(self, rows_for):
            self.rows_for, self.sql_prompts = rows_for, []

        def json(self, role, system, user, max_tokens=2048, think=None):
            if role == "planner":
                return {"questions": ["cardiology waiting times in Pankow"], "specialty": "Cardiology"}
            if role == "sql":
                self.sql_prompts.append(user)
                # ignores the filter it was told to use, like the live run did
                return {"sql": "SELECT p.name, w.channel, w.days_to_appointment FROM FT_PRACTICES.practices p "
                               f"JOIN FT_WAITS.waits w ON p.practice_id = w.practice_id WHERE p.specialty = '{self.rows_for}'"}
            if role == "answer":
                return {"routes": [{"route": "Phone the practice", "expected_days": 45, "why": "x", "evidence": ["E1"]}]}
            return {"keep": [0]}  # a lenient verifier keeps it

    def run_case(self, rows_for):
        llm = self.Cardio(rows_for)
        with tempfile.TemporaryDirectory() as d:
            out = investigate("Kardiologe in Pankow", llm, LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
        return llm, out

    def test_dermatology_rows_cited_for_cardiology_are_dropped(self):
        llm, out = self.run_case("dermatology")
        self.assertIn("lower(p.specialty) = 'cardiology'", llm.sql_prompts[0])
        self.assertEqual(out["routes"], [])
        self.assertEqual(out["dropped"][0]["reason"], "cites dermatology rows, but the patient needs cardiology")
        self.assertEqual(out["trace"]["steps"][0]["specialty"], "cardiology")

    def test_cardiology_rows_are_kept(self):
        _, out = self.run_case("cardiology")
        self.assertEqual([r["route"] for r in out["routes"]], ["Phone the practice"])


class CatalogueTests(unittest.TestCase):
    """WO-FT-REVIEW-01 part 1: exact values, nicknames, one redraft when a query finds nothing."""

    def test_nickname_finds_the_borough(self):
        from fasttrack.sources import canonical_sql

        sql = "SELECT practice_id FROM FT_PRACTICES.practices WHERE district = 'Köpenick' AND specialty = 'orthopaedics'"
        self.assertEqual(LocalSource().query(sql), [])
        self.assertEqual(LocalSource().query(canonical_sql(sql)), [{"practice_id": "P01"}])
        self.assertIn("lower(specialty) = 'ent'", canonical_sql("... lower(specialty) = 'hno'"))

    def test_prompt_lists_the_stored_values(self):
        from fasttrack.agent import SQL

        for value in ("'Treptow-Köpenick'", "'Friedrichshain-Kreuzberg'", "'ENT'", "'gynaecology'", "'appointment service'", "'GP referral'"):
            self.assertIn(value, SQL)

    def test_empty_select_is_redrafted_once(self):
        sql_users = []

        class Empty(FakeLLM):
            def json(self, role, system, user, max_tokens=2048, think=None):
                if role == "sql" and "rules" not in user:
                    sql_users.append(user)
                    if "0 rows" in user:
                        return {"sql": "SELECT p.practice_id, p.name FROM FT_PRACTICES.practices p WHERE p.district LIKE '%Köpenick%' AND p.specialty = 'orthopaedics'"}
                    return {"sql": "SELECT p.practice_id, p.name FROM FT_PRACTICES.practices p WHERE p.district = 'Koepenick-Süd'"}
                return super().json(role, system, user, max_tokens)

        with tempfile.TemporaryDirectory() as d:
            out = investigate("knee, Köpenick", Empty(), LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
        self.assertEqual(len(sql_users), 2)
        q = out["trace"]["steps"][1]["queries"][0]
        self.assertEqual(q["attempts"][0]["rows"], 0)
        self.assertIn("LIKE", q["sql"])
        self.assertEqual(out["evidence"]["E1"]["row"]["practice_id"], "P01")


class RulesTests(unittest.TestCase):
    """WO-FT-REVIEW-01 part 2: every run reads the rules, even when the planner forgets them."""

    class PracticesOnly(FakeLLM):
        def json(self, role, system, user, max_tokens=2048, think=None):
            if role == "planner":
                return {"questions": ["orthopaedics practices in Treptow-Köpenick"]}
            if role == "answer":
                return {"routes": [{"route": "Appointment service", "expected_days": None, "why": "x", "evidence": ["E3"]}]}
            return super().json(role, system, user, max_tokens)

    def test_rules_query_is_added(self):
        with tempfile.TemporaryDirectory() as d:
            out = investigate("knee, Köpenick", self.PracticesOnly(), LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
        queries = out["trace"]["steps"][1]["queries"]
        self.assertTrue(queries[-1]["fixed"])
        self.assertEqual(len(queries[-1]["evidence"]), 7)
        self.assertIn("rule_id", out["evidence"]["E3"]["row"])  # two practice rows, then the rules

    def test_planned_rules_query_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as d:
            out = investigate("knee, Köpenick", FakeLLM(), LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
        self.assertFalse(any(q.get("fixed") for q in out["trace"]["steps"][1]["queries"]))

    def test_sql_prompt_says_which_table_answers_what(self):
        from fasttrack.agent import SQL

        self.assertIn("116117", SQL)
        self.assertIn("-> FT_RULES.rules", SQL)


class RevisionTests(unittest.TestCase):
    """WO-FT-REVIEW-01 part 3: one rewrite when the verifier keeps nothing, never otherwise."""

    class Counting(FakeLLM):
        def __init__(self, verdicts):
            self.verdicts, self.answers, self.answer_users = list(verdicts), 0, []

        def json(self, role, system, user, max_tokens=2048, think=None):
            if role == "answer":
                self.answers += 1
                self.answer_users.append(user)
            if role == "verifier":
                return self.verdicts.pop(0)
            return super().json(role, system, user, max_tokens)

    def run_with(self, *verdicts):
        llm = self.Counting(verdicts)
        with tempfile.TemporaryDirectory() as d:
            out = investigate("knee, Köpenick", llm, LocalSource(), LocalStore(Path(d) / "m.jsonl"), search=False)
        return llm, out

    def test_nothing_kept_gets_one_revision(self):
        llm, out = self.run_with({"keep": [], "notes": ["over-claims", "no row"]}, {"keep": [0]})
        self.assertEqual(llm.answers, 2)
        self.assertIn("over-claims", llm.answer_users[1])
        self.assertEqual([r["route"] for r in out["routes"]], ["Open consultation"])
        steps = [s["step"] for s in out["trace"]["steps"]]
        self.assertEqual(steps[-3:], ["verify", "revise", "verify"])
        self.assertTrue(out["dropped"][-1]["revision"])

    def test_second_empty_verdict_is_final(self):
        llm, out = self.run_with({"keep": []}, {"keep": []})
        self.assertEqual(llm.answers, 2)
        self.assertEqual(out["routes"], [])

    def test_kept_route_means_no_revision(self):
        llm, out = self.run_with({"keep": [0]})
        self.assertEqual(llm.answers, 1)
        self.assertNotIn("revise", [s["step"] for s in out["trace"]["steps"]])
