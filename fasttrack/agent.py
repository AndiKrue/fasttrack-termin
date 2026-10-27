# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""The explain-why loop: plan -> query the sources -> recall -> answer -> verify -> remember.

Every claim in the final answer cites evidence ids. An evidence id names one row of one SQL
result (`E3` = row 3 of all rows returned), so a reader can open the trace and see the exact
query and row behind each sentence. Claims the verifier cannot tie to evidence are removed.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
import uuid

from .memory import open_memory, stamp
from .sources import SCHEMA, open_source
from .web import open_search, web_evidence

PLANNER = (
    "You help statutory-insurance patients in Berlin reach a specialist appointment fast. "
    "Plan which facts are needed from three databases to answer the patient's question: "
    "the rules of the appointment system, the practice directory, and observed waiting times. "
    'Return {"questions": [up to 5 short questions, each answerable by one SQL query]}.'
)
SQL = (
    "Write one read-only SQL SELECT for the question, using only these tables and columns:\n"
    + SCHEMA
    + "Use the schema-qualified names exactly as shown. No semicolon. "
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
    "statement in it is supported by its cited rows. "
    'Return {"keep": [indexes of supported routes], "notes": ["why a route was dropped"]}.'
)


def investigate(question: str, llm, source=None, memory=None, search=None, on_step=None) -> dict:
    source = source or open_source()
    memory = memory or open_memory()
    run_id = uuid.uuid4().hex[:8]
    notify = on_step or (lambda step: None)
    trace = {"run_id": run_id, "question": question, "source": source.name, "memory": memory.name, "steps": []}

    plan = llm.json("planner", PLANNER, question)
    questions = [q for q in plan.get("questions", []) if isinstance(q, str)][:5]
    _add(trace, notify, {"step": "plan", "questions": questions})

    search = open_search() if search is None else (search or None)
    # Model calls are the slow part: write every SQL query and run the web search at the same time.
    # The database queries themselves stay sequential on the one JDBC connection.
    with ThreadPoolExecutor(max_workers=len(questions) + 1) as pool:
        drafts = [pool.submit(lambda q=q: llm.json("sql", SQL, q)["sql"]) for q in questions]
        web = pool.submit(web_evidence, question, llm, search) if search is not None else None

        evidence, queries = {}, []
        for q, draft_sql in zip(questions, drafts):
            try:
                sql = draft_sql.result()
                rows = source.query(sql)
            except Exception as exc:  # a bad query is recorded, never fatal
                queries.append({"question": q, "error": f"{type(exc).__name__}: {exc}"[:300]})
                continue
            ids = []
            for row in rows:
                eid = f"E{len(evidence) + 1}"
                evidence[eid] = {"sql": sql, "row": row}
                ids.append(eid)
            queries.append({"question": q, "sql": sql, "evidence": ids})
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
        f"Routes: {json.dumps(routes, ensure_ascii=False)}\nRows: {json.dumps(cited, ensure_ascii=False)}",
    )
    keep = {i for i in verdict.get("keep", []) if isinstance(i, int)}
    kept = [r for i, r in enumerate(routes) if i in keep and r["evidence"]]
    notes = [n for n in verdict.get("notes", []) if isinstance(n, str)]
    dropped = []
    for i, r in enumerate(routes):
        if i in keep and r["evidence"]:
            continue
        reason = "no cited evidence row exists" if not r["evidence"] else "verifier found the cited rows do not support it"
        dropped.append({"route": r.get("route"), "why": r.get("why"), "reason": reason})
    if len(notes) == len(dropped):  # one note per dropped route: pair them in order
        for d, n in zip(dropped, notes):
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
        "model_calls": getattr(llm, "calls", []),
    }


def _add(trace: dict, notify, step: dict) -> None:
    """Record a step and tell a live listener (UI stream, Telegram) about it."""
    trace["steps"].append(step)
    try:
        notify(step)
    except Exception:  # a broken listener never breaks the investigation
        pass
