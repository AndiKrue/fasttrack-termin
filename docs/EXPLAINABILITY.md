# Explainability: The Agent That Can Explain Why

FastTrack Termin's Track 02 explanation is a path from a proposed appointment route to its cited evidence rows. A judge can inspect the source, fields, SQL or URL, and what the verifier removed. This is evidence provenance and a workflow trace, not access to a model's internal reasoning.

This document describes code on `origin/main` at **`732a83b9b162f165af0643dabdeace6691b0742b`**. All source-file links below are pinned to that commit. The relevant feature commits are:

| Change | Commit | Implementation |
| --- | --- | --- |
| Route explanations, removed routes and model-call table | [446aa574a5779520031efbbe9f61446aa77440d6](https://github.com/AndiKrue/fasttrack-termin/commit/446aa574a5779520031efbbe9f61446aa77440d6) | [fasttrack/agent.py][agent], [fasttrack/static/app.js][ui] |
| Concurrent SQL drafting and web work; sequential database execution | [6e8e86d8958146a960e9373021c4467b88374fc8](https://github.com/AndiKrue/fasttrack-termin/commit/6e8e86d8958146a960e9373021c4467b88374fc8) | [fasttrack/agent.py][agent], `investigate()` |
| Ultra fallback after JSON parsing failures | [b3981903241266cf35b0fa2fc9b77babf146c32b](https://github.com/AndiKrue/fasttrack-termin/commit/b3981903241266cf35b0fa2fc9b77babf146c32b) | [fasttrack/llm.py][llm], `Nemotron.json()` |

## How one answer is built

The orchestration below is implemented by `investigate()` in [fasttrack/agent.py][agent].

1. **Plan.** The planner produces source questions about appointment rules, practices and waiting times. The code keeps string questions, capped by the implementation. The plan is recorded in `trace.steps`.
2. **Draft SQL and search concurrently.** A thread pool submits one SQL-generation call per planned question. If web search is configured, `web_evidence()` runs alongside those calls. Database queries execute one by one on the source connection, in planned-question order. Concurrent drafting does not mean concurrent JDBC queries.
3. **Assign SQL evidence IDs.** Each returned row receives the next ID, `E1`, `E2`, and so on, within this investigation. Its evidence entry contains the exact `sql` and `row`. SQL can query `FT_RULES.rules`, `FT_PRACTICES.practices` and `FT_WAITS.waits`, including cross-source joins. Failed drafts or queries are recorded rather than used as evidence.
4. **Add web rows with URLs.** [fasttrack/web.py][web] uses the `sql` model role to write one search query for the patient question, then the `verifier` role to extract practice facts from returned pages. The extraction prompt requires stated facts and nulls for unstated fields. Only rows whose URL matches a returned page URL are accepted. They receive IDs from the same sequence, a `row`, a source `url`, and a `sql` field containing `web search: <query>`. Web failures are traced without aborting the remaining workflow.
5. **Recall.** Memory returns earlier findings as answer context. Recall is recorded by its returned-record count. Earlier memories do not become new evidence IDs: the citation filter accepts only IDs in this investigation's evidence dictionary. See [fasttrack/memory.py][memory].
6. **Answer with evidence IDs.** The answer prompt asks Nemotron Ultra to rank routes and supply `route`, `expected_days`, `why` and an `evidence` list. It instructs the model to use only the supplied evidence rows, prefer web rows carrying URLs, identify SAMPLE facts, and avoid medical advice. The answer's citations are evidence IDs, which the UI resolves to SQL or source links.
7. **Verify and remove.** Unknown IDs are stripped first. The verifier receives the routes and their cited rows, and returns indexes to keep plus notes. A route survives only if its index is selected and at least one valid citation remains. The result exposes rejected routes in `dropped`, string notes in `verifier_notes`, and a `why_trace` for each retained route. Each `why_trace` entry contains `eid`, `sql_or_query` and `url`; full row fields remain in `evidence`.
8. **Remember retained findings.** Only retained routes are passed to `memory.remember()`, with the question, run ID, timestamp, route, reason and cited evidence. The JSONL store retains that record. The current [meterless/bridge.ts][bridge] stores route/reason text, a run tag and run-level source in H-MEM with its ledger; it does not persist the full evidence payload.

These steps describe the code's checks and prompts. A model's verification verdict is not independent proof that every sentence is true. Caveats are returned from the answer and are not separately checked by the route verifier. [Source: fasttrack/agent.py][agent].

## Worked example from the tests

This example comes from `FakeLLM` and `AgentTests.test_federated_join_and_citations` in [tests/test_agent.py][tests]. The input is `knee, Köpenick`; the test uses `LocalSource`, temporary JSONL memory and `search=False`. It does not call live Zetaris, NVIDIA or Firecrawl services.

The fixture deliberately returns placeholder reasons `x` and `y`. It tests citation filtering and memory, not the quality of a medical or factual explanation. Its `expected_days` values are test output, not appointment promises. The joined practice/wait inputs are **SAMPLE data** from [data/seed/practices.csv][practices] and [data/seed/waits.csv][waits].

| Claim in the fixture's draft | Evidence ID | SQL or URL | Row and outcome |
| --- | --- | --- | --- |
| `route: Open consultation`, `expected_days: 0`, `why: x` | `E1` | `SELECT p.name, w.channel, w.days_to_appointment FROM FT_PRACTICES.practices p JOIN FT_WAITS.waits w ON p.practice_id = w.practice_id WHERE p.specialty = 'orthopaedics' AND p.district = 'Treptow-Köpenick'` | `{"name":"Sample Practice Orthopaedics Köpenick","channel":"open consultation","days_to_appointment":0}`. The route retains `E1`; the fixture's verifier selects it. |
| The same draft also cites an unknown row | `E9` | None: no such evidence row was returned in this fixture | The ID is stripped. The route still has `E1`. |
| `route: Invented`, `expected_days: 1`, `why: y` | `E99` | None: no such evidence row exists | After citation filtering the route has no evidence and is removed, even though `FakeLLM` selects its index to keep. |

`AgentTests.test_dropped_route_is_explained` adds a stricter fake verifier. It asserts that `Invented` appears in `dropped`, its reason is `no cited evidence row exists`, its note is `Invented: no row supports it`, and the retained route's first `why_trace` entry names `E1`. These are separate test fixtures; the base fixture returns no verifier notes. [Source: tests/test_agent.py][tests].

The SQL above does not select the seed `sample` column. Its sample status follows from the seed files and sample practice name; the example must not be presented as a live availability result.

## What the judge can inspect

The web UI is implemented in [fasttrack/static/app.js][ui]. Its displays expose the following evidence boundaries:

| UI control | What the implementation shows |
| --- | --- |
| **Why this route** | `whyBlock()` renders one entry per cited evidence row. `sourceName()` extracts tables following SQL `FROM`/`JOIN`, or the host of a web URL. `factLine()` shows non-empty row fields other than `url`, capped by the implementation. The entry includes the SQL or source URL. |
| **Evidence chip** | Expands the query and complete row JSON; URL-backed evidence also has an **Open source** link. |
| **Removed by the verifier** | `renderResult()` shows each dropped route and its paired note or default rejection reason. Notes are paired with dropped routes only when their counts match; otherwise the UI can display the general `verifier_notes`. |
| **Model calls** | Role, model, seconds and tokens in/out from `model_calls`. Missing token counts display as `?`. This is call metadata, not a benchmark or an explanation of internal model reasoning. |
| **Trace: every step, query and verifier note** | The recorded `trace.steps`, including the plan, query results/errors, optional web step, recalled-record count and verifier summary. |

The source label derived from SQL says `Zetaris` even when the local SQLite stand-in answers the query. Check `trace.source` and the footer for the actual backend, rather than treating that label as evidence of a live Zetaris run. [Sources: fasttrack/static/app.js][ui], [fasttrack/sources.py][sources].

## What it refuses, and how

| Boundary | Enforcement in code | Limit |
| --- | --- | --- |
| Non-SELECT or prohibited SQL | `check_sql()` requires a SELECT prefix and rejects its prohibited keyword pattern and remaining statement separators. Both source backends call it before executing queries. | This is a string-based guard. Trailing semicolons are stripped before validation. See [fasttrack/sources.py][sources]. |
| Uncited claims/routes | `investigate()` strips nonexistent evidence IDs and drops routes with no valid citations. The verifier is instructed to reject routes with any unsupported factual statement. | The deterministic check operates on citation existence and route selection; support for individual claims within a cited route is a model judgment. See [fasttrack/agent.py][agent]. |
| Excluded booking portals | `FirecrawlSearch.search()` adds site exclusions for doctolib, jameda, docinsider and sanego, then drops returned URLs containing the configured portal-name substrings. | This is an explicit blocklist, not a general audit of every website's terms. See [fasttrack/web.py][web]. |
| Medical advice | The answer prompt says never to give medical advice and to point emergencies to **112**. The web UI also displays that disclaimer. | This is a prompt and user-facing warning, not a separate deterministic medical-content classifier. See [fasttrack/agent.py][agent] and [fasttrack/static/index.html][index]. |

Seed practices and waiting times remain SAMPLE data. Appointment rules carry the legal basis listed in [data/seed/rules.csv][rules]; the agent does not independently validate current law.

## When a model does not return JSON

`Nemotron.json()` in [fasttrack/llm.py][llm] first calls the configured role model. If parsing fails, it retries that role with an instruction to output JSON immediately. After another parsing failure, it makes one final attempt using `FALLBACK`, provided the configured role model differs from the fallback. With the defaults, this means a Lightning role can fall back to Ultra; the answer role already uses Ultra. `FT_MODEL_FALLBACK` can override the fallback model.

This is a response-format recovery path, not a general retry for every API error or a factual correctness check. `FallbackTest.test_ultra_answers_after_two_lightning_misses` in [tests/test_llm.py][llmtests] checks the default fallback sequence. Successful HTTP responses contribute call metadata through `Nemotron.chat()`, including attempts that subsequently fail JSON parsing.

[agent]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/agent.py
[sources]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/sources.py
[web]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/web.py
[memory]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/memory.py
[bridge]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/meterless/bridge.ts
[ui]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/app.js
[index]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/index.html
[llm]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/llm.py
[tests]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/tests/test_agent.py
[llmtests]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/tests/test_llm.py
[practices]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/data/seed/practices.csv
[waits]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/data/seed/waits.csv
[rules]: https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/data/seed/rules.csv
