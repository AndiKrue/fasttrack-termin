# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""The explain-why loop: plan -> query the sources -> recall -> answer -> verify -> remember.

Every claim in the final answer cites evidence ids. An evidence id names one row of one SQL
result (`E3` = row 3 of all rows returned), so a reader can open the trace and see the exact
query and row behind each sentence. Claims the verifier cannot tie to evidence are removed.
"""

from __future__ import annotations

import csv
import json
from concurrent.futures import ThreadPoolExecutor
import uuid

from .memory import open_memory, stamp
from .sources import SCHEMA, SEED, canonical_sql, open_source
from .web import open_search, web_evidence


def _values(table: str, column: str) -> list[str]:
    """The allowed values of one column, read from the seed so the prompts follow the data."""
    with open(SEED / f"{table}.csv", encoding="utf-8", newline="") as f:
        return sorted({row[column] for row in csv.DictReader(f)})


SPECIALTIES = _values("practices", "specialty")
DISTRICTS = _values("practices", "district")
TOPICS = _values("rules", "topic")
CHANNELS = _values("waits", "channel")
REDRAFT = "\nThis query returned 0 rows:\n{sql}\nRelax the district or name filter (LIKE or IN); keep the specialty filter."
# Seven rows: when no planned query reached the rules, all of them are read.
RULES_QUESTION = "Which rules of the appointment system apply?"
RULES_SQL = "SELECT rule_id, topic, rule, legal_basis FROM FT_RULES.rules"

PLANNER = (
    "You help statutory-insurance patients in Berlin reach a specialist appointment fast. "
    "Plan which facts are needed from three databases to answer the patient's question: "
    "the rules of the appointment system, the practice directory, and observed waiting times. "
    'Return {"questions": [up to 5 short questions, each answerable by one SQL query], '
    f'"specialty": the one specialty the patient needs, exactly one of {", ".join(SPECIALTIES)}, or null}}.'
)
SQL = (
    "Write one read-only SQL SELECT for the question, using only these tables and columns:\n"
    + SCHEMA
    + "Values, spelled exactly like this: specialty is one of "
    + ", ".join(f"'{v}'" for v in SPECIALTIES)
    + "; district is one of "
    + ", ".join(f"'{v}'" for v in DISTRICTS)
    + " (never 'Berlin'; Köpenick is 'Treptow-Köpenick'); rules topic is one of "
    + ", ".join(f"'{v}'" for v in TOPICS)
    + "; channel is one of "
    + ", ".join(f"'{v}'" for v in CHANNELS)
    + "; accepts_new_patients and online_booking "
    "are the strings 'yes' or 'no'; days_to_appointment is a number. Join waits to practices on practice_id. "
    "Prefer simple filters (lower(specialty) = '...') over subqueries.\n"
    "Which table answers what: rules, patient rights, 116117, the appointment service, referrals, urgency codes "
    "and open consultation duties -> FT_RULES.rules; practices by district or specialty -> FT_PRACTICES.practices; "
    "waiting days and booking channels -> FT_WAITS.waits joined to practices on practice_id.\n"
    "Use the schema-qualified table names exactly as shown and give each table a short alias "
    "(FROM FT_PRACTICES.practices p JOIN FT_WAITS.waits w ...); qualify columns with the alias only, "
    "never as schema.table.column. No semicolon. "
    'Return {"sql": "..."}.'
)
ANSWER = (
    "Recommend the fastest routes to a specialist appointment for this patient, best first. "
    "Use only the evidence rows given; cite them by id. Prefer real practices from web rows (they carry a url) "
    "over SAMPLE rows, and say plainly when a fact comes from sample data. "
    "Never give medical advice; in an emergency point to 112. "
    'Return {"routes": [{"route": "...", "expected_days": number or null, '
    '"why": "...", "evidence": ["E1", ...]}], "caveats": ["..."]}.'
)
VERIFY = (
    "Check each route against the cited evidence rows. Keep a route only if every factual "
    "statement in it is supported by its cited rows, and drop a route whose rows are about a different "
    "specialty than the patient needs. "
    'Return {"keep": [indexes of supported routes], "notes": ["why a route was dropped"]}.'
)


def investigate(question: str, llm, source=None, memory=None, search=None, on_step=None) -> dict:
    source = source or open_source()
    memory = memory or open_memory()
    run_id = uuid.uuid4().hex[:8]
    first_call = len(getattr(llm, "calls", []))  # the client is shared across requests: report only this run's calls
    notify = on_step or (lambda step: None)
    trace = {"run_id": run_id, "question": question, "source": source.name, "memory": memory.name, "steps": []}

    plan = llm.json("planner", PLANNER, question)
    questions = [q for q in plan.get("questions", []) if isinstance(q, str)][:5]
    specialty = _specialty(plan.get("specialty"))
    _add(trace, notify, {"step": "plan", "questions": questions, "specialty": specialty})

    search = open_search() if search is None else (search or None)
    # Model calls are the slow part: write every SQL query and run the web search at the same time.
    # The database queries themselves stay sequential on the one JDBC connection.
    with ThreadPoolExecutor(max_workers=len(questions) + 1) as pool:
        drafts = [pool.submit(lambda q=q: llm.json("sql", SQL, _for_specialty(q, specialty))["sql"]) for q in questions]
        web = pool.submit(web_evidence, question, llm, search) if search is not None else None

        evidence, queries = {}, []
        for q, draft_sql in zip(questions, drafts):
            attempts = []  # a query that found nothing, before its one redraft
            try:
                sql = canonical_sql(draft_sql.result())
                rows = source.query(sql)
                if not rows:
                    attempts.append({"sql": sql, "rows": 0})
                    sql = canonical_sql(llm.json("sql", SQL, _for_specialty(q, specialty) + REDRAFT.format(sql=sql))["sql"])
                    rows = source.query(sql)
            except Exception as exc:  # a bad query is recorded, never fatal
                queries.append({"question": q, "error": f"{type(exc).__name__}: {exc}"[:300], **({"attempts": attempts} if attempts else {})})
                continue
            queries.append({"question": q, "sql": sql, "evidence": _cite(evidence, sql, rows), **({"attempts": attempts} if attempts else {})})
        if not any("ft_rules." in x.get("sql", "").lower() and x["evidence"] for x in queries if "sql" in x):
            # The planner left the rules out, but they decide most routes (116117, referral, open consultation).
            try:
                queries.append({"question": RULES_QUESTION, "sql": RULES_SQL, "evidence": _cite(evidence, RULES_SQL, source.query(RULES_SQL)), "fixed": True})
            except Exception as exc:
                queries.append({"question": RULES_QUESTION, "error": f"{type(exc).__name__}: {exc}"[:300], "fixed": True})
        _add(trace, notify, {"step": "query", "queries": queries})

        if web is not None:
            try:
                web_query, practices = web.result()
                for row in practices:
                    eid = f"E{len(evidence) + 1}"
                    evidence[eid] = {"sql": f"web search: {web_query}", "url": row.get("url"), "row": row}
                _add(trace, notify, {"step": "web", "query": web_query, "practices": len(practices)})
            except Exception as exc:  # the web is optional evidence, never fatal
                _add(trace, notify, {"step": "web", "error": f"{type(exc).__name__}: {exc}"[:300]})
    trace["web"] = getattr(search, "name", None)

    recalled = memory.recall(question)
    _add(trace, notify, {"step": "recall", "records": len(recalled)})

    rows_text = json.dumps({k: v["row"] for k, v in evidence.items()}, ensure_ascii=False)
    prior = json.dumps(recalled, ensure_ascii=False)
    draft = llm.json(
        "answer",
        ANSWER,
        f"Patient question: {question}\nEvidence rows: {rows_text}\nEarlier verified findings: {prior}",
        max_tokens=8192,
    )
    routes = [r for r in draft.get("routes", []) if isinstance(r, dict)]
    for r in routes:  # citations must name real evidence
        r["evidence"] = [e for e in r.get("evidence", []) if e in evidence]

    cited = {e: evidence[e]["row"] for r in routes for e in r["evidence"]}
    verdict = llm.json(
        "verifier",
        VERIFY,
        f"Patient needs: {specialty or 'not stated'}\n"
        f"Routes: {json.dumps(routes, ensure_ascii=False)}\nRows: {json.dumps(cited, ensure_ascii=False)}",
    )
    keep = {i for i in verdict.get("keep", []) if isinstance(i, int)}
    off = _off_specialty(routes, evidence, specialty, source)
    kept = [r for i, r in enumerate(routes) if i in keep and r["evidence"] and i not in off]
    notes = [n for n in verdict.get("notes", []) if isinstance(n, str)]
    dropped, unexplained = [], []
    for i, r in enumerate(routes):
        if i in keep and r["evidence"] and i not in off:
            continue
        if not r["evidence"]:
            reason = "no cited evidence row exists"
        elif i in off:
            reason = f"cites {off[i]} rows, but the patient needs {specialty}"
        else:
            reason = "verifier found the cited rows do not support it"
        dropped.append({"route": r.get("route"), "why": r.get("why"), "reason": reason})
        if i not in off or i not in keep:
            unexplained.append(dropped[-1])
    if len(notes) == len(unexplained):  # one note per route the verifier dropped: pair them in order
        for d, n in zip(unexplained, notes):
            d["note"] = n
    for r in kept:  # the plain path from each claim back to its source
        r["why_trace"] = [{"eid": e, "sql_or_query": evidence[e]["sql"], "url": evidence[e].get("url")} for e in r["evidence"]]
    _add(trace, notify, {"step": "verify", "kept": len(kept), "dropped": len(routes) - len(kept), "notes": verdict.get("notes", [])})

    for r in kept:
        memory.remember({"run_id": run_id, "at": stamp(), "question": question, "route": r["route"], "why": r["why"], "evidence": {e: evidence[e] for e in r["evidence"]}})

    return {
        "run_id": run_id,
        "routes": kept,
        "caveats": draft.get("caveats", []),
        "dropped": dropped,
        "verifier_notes": notes,
        "evidence": {e: evidence[e] for r in kept for e in r["evidence"]},
        "trace": trace,
        "model_calls": getattr(llm, "calls", [])[first_call:],
    }


def _cite(evidence: dict, sql: str, rows: list[dict]) -> list[str]:
    """Give each row the next evidence id; return the ids."""
    ids = []
    for row in rows:
        eid = f"E{len(evidence) + 1}"
        evidence[eid] = {"sql": sql, "row": row}
        ids.append(eid)
    return ids


def _specialty(value) -> str | None:
    """The planner's specialty as it is written in the data, or None when it names none of them."""
    wanted = str(value or "").strip().lower()
    return next((s for s in SPECIALTIES if s.lower() == wanted), None)


def _for_specialty(question: str, specialty: str | None) -> str:
    if not specialty:
        return question
    return (
        f"{question}\nThe patient needs {specialty}. Every query on practices or waiting times filters "
        f"lower(p.specialty) = '{specialty.lower()}' (join waits to practices for it); the rule table needs no such filter."
    )


def _off_specialty(routes: list[dict], evidence: dict, specialty: str | None, source) -> dict[int, str]:
    """Routes that cite a database row of another specialty: {route index: that specialty}.

    A row names its specialty directly, or through its practice id, practice name or wait
    observation id. Web rows (they carry a url) are free text and are left to the verifier.
    """
    if not specialty:
        return {}
    owner = {}
    try:
        for p in source.query("SELECT practice_id, name, specialty FROM FT_PRACTICES.practices"):
            p = {str(k).lower(): v for k, v in p.items()}
            owner[p["practice_id"]] = owner[p["name"]] = str(p["specialty"]).lower()
        for w in source.query("SELECT observation_id, practice_id FROM FT_WAITS.waits"):
            w = {str(k).lower(): v for k, v in w.items()}
            if w["practice_id"] in owner:
                owner[w["observation_id"]] = owner[w["practice_id"]]
    except Exception:  # without the lookup only rows with their own specialty column are checked
        pass
    off = {}
    for i, r in enumerate(routes):
        for e in r["evidence"]:
            if evidence[e].get("url"):
                continue
            row = {str(k).lower(): v for k, v in evidence[e]["row"].items()}
            found = row.get("specialty") or next(
                (owner[row[k]] for k in ("practice_id", "observation_id", "name") if row.get(k) in owner), None
            )
            if found and str(found).lower() != specialty.lower():
                off[i] = str(found).lower()
                break
    return off


def _add(trace: dict, notify, step: dict) -> None:
    """Record a step and tell a live listener (UI stream, Telegram) about it."""
    trace["steps"].append(step)
    try:
        notify(step)
    except Exception:  # a broken listener never breaks the investigation
        pass
