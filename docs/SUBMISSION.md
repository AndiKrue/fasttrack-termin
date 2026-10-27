# Open Agent Hackathon 2026: submission texts

Each section below is ready to paste into the corresponding form field. Model names describe the defaults in the code; runtime overrides must be disclosed if used.

## Project name

FastTrack Termin

## Track

Track 02: The Agent That Can Explain Why

## Short description

FastTrack Termin helps statutory-insurance patients in Berlin identify the fastest supported route to a specialist appointment. It combines appointment-system rules, a practice directory and waiting-time observations, explains each route with SQL evidence rows, checks the draft with a separate verifier, and recalls earlier verified findings through Meterless H-MEM. Practices and waiting times are SAMPLE data. This is not medical advice.

## Problem and users

A patient needs an actionable next step, but appointment rules, practice information and waiting-time observations live in different sources. A plausible recommendation is insufficient if the patient cannot inspect why it applies to their situation.

FastTrack Termin is built for statutory-insurance patients in Berlin asking how to reach a specialist appointment. It plans the facts needed, queries the sources, ranks supported routes and shows a “Why” explanation alongside supporting evidence rows. SQL evidence includes the exact query; optional web evidence includes its source URL. The prototype demonstrates appointment navigation using SAMPLE practices and waiting times; it does not establish real availability, book appointments or give medical advice.

## Why Track 02 fits

The explanation is tied to inspectable data. Each returned SQL row receives an evidence ID. The answer role must cite those IDs, and the application removes references that do not exist in the current evidence map. A separate verifier role then checks the proposed routes against the cited rows. The application retains only routes selected by that verifier that also have evidence references.

The user sees the route, its reason and the actual evidence rows. For database evidence, the supporting SQL is shown; optional web evidence carries a source URL. The trace records the plan, queries, recall count and verifier outcome. Only retained routes enter memory. “Verified” here means accepted by the model verifier against the supplied rows, not independently validated medical or legal guidance.

## How we integrated Zetaris

Zetaris Lightning supplies a federated SQL surface across three logical sources: FT_RULES.rules, FT_PRACTICES.practices and FT_WAITS.waits. In fasttrack/sources.py, the agent's generated SQL is executed through JayDeBeApi using com.zetaris.lightning.jdbc.LightningDriver and the configured Lightning JDBC connection. A guard restricts agent queries to a single read-only SELECT.

zetaris/register.py copies the seed CSV files into the platform's driver container, registers each source as a Lightning database with a CSV filestore table, and reads back row counts over JDBC. The integration therefore connects the reasoning loop to executable queries across separate rule, directory and waiting-time sources. Each evidence entry retains the SQL and its returned row.

The supplied practice-directory and waiting-time tables are SAMPLE data. The code also provides a local SQLite stand-in with the same qualified table names. That fallback is labelled local-sqlite in the trace; it must not be presented as a Zetaris execution.

An optional Firecrawl path in fasttrack/web.py can add URL-backed practice evidence. These web rows are distinct from the SAMPLE seed tables and do not establish live appointment availability. The SQL role also forms the search query, and the verifier role extracts page facts before the final route-verification step.

## How we integrated Meterless H-MEM

fasttrack/memory.py connects Python to Meterless H-MEM through meterless/bridge.ts, a TypeScript bridge using JSON on standard input and output. After verification, the agent passes each retained route, reason, question, timestamp, run ID and supporting evidence to the memory adapter.

The current H-MEM bridge stores the route and reason as a factual working-memory item, adds a run tag and a fasttrack:<run_id> source, and persists H-MEM state and its ledger under runs/hmem by default. It returns the item's ledger action history when remembering. The bridge preserves run-level provenance; it does not currently copy the full SQL evidence payload into H-MEM. Full evidence remains in the investigation response.

On the next question, the bridge queries H-MEM and returns matching content, source and relevance. The answer role receives these earlier verified findings alongside fresh SQL evidence. Recalled memory is context, not a substitute for current evidence: the new answer still passes through citation filtering and verification.

The trace identifies meterless-h-mem when this integration is active. A separately labelled local-jsonl fallback exists for offline use and is not evidence of a Meterless run.

## NVIDIA contribution and model allocation

FastTrack Termin uses the NVIDIA OpenAI-compatible API through fasttrack/llm.py. Its four roles have explicit model defaults:

| Role | Default model | Responsibility |
| --- | --- | --- |
| Planner | nvidia/nemotron-3.5-lightning-30b-a3b | Plan which facts to retrieve. |
| SQL | nvidia/nemotron-3.5-lightning-30b-a3b | Produce a read-only SELECT for each planned question. |
| Answer | nvidia/nemotron-3-ultra-550b-a55b | Rank appointment routes and explain them with evidence IDs. |
| Verifier | nvidia/nemotron-3.5-lightning-30b-a3b | Check route claims against cited evidence rows. |

FT_MODEL_PLANNER, FT_MODEL_SQL, FT_MODEL_ANSWER and FT_MODEL_VERIFIER allow per-role overrides. The client records role, model, elapsed time and reported input/output token usage for successful calls. Console lines report role, model, HTTP status and elapsed time. These are implementation capabilities, not benchmark results.

## Best use of Nemotron

Nemotron drives the complete reasoning loop, including the check on its own proposed answer. Lightning 30B plans the information needed, translates each retrieval question into SQL over the federated schema, and later acts as the separate verifier. Ultra 550B receives the patient's question, current evidence rows and recalled findings to rank routes and write their reasons with evidence IDs. This role allocation reserves Ultra for the evidence-synthesis step while giving Lightning explicit planning, retrieval and checking responsibilities. Crucially, generation does not end the workflow: the application filters invalid citations and only releases routes retained by the verifier with supporting evidence references. The same retained routes become future memory. Per-role model selection and call records make this design inspectable, without claiming unmeasured speed, cost or accuracy gains.

## What is unique about our use of sponsor technology?

The sponsor integrations form one evidence loop. Zetaris provides the queryable facts across three logical sources. Nemotron decides what to retrieve, generates SQL, explains the resulting options and checks its draft. Meterless H-MEM retains accepted route explanations with run provenance and a ledger, then recalls them for the next question.

The useful distinction is the link between explanation and retrieval: a route's “why” comes with the SQL row used to support it. Memory helps continuity, while the next answer must still cite fresh evidence and pass verification. The current H-MEM bridge stores route text and run provenance rather than the full evidence bundle. Source and memory backend labels make the real integrations distinguishable from local fallbacks.

## Cursor use

Cursor was not used.

## Pre-existing components and attribution

No pre-existing components of our own were reused. Meterless H-MEM is a third-party component vendored unmodified in meterless/hmem under Apache-2.0; its licence is retained there. FastTrack Termin's application and integration code is provided in this public AGPL-3.0 repository. We do not claim authorship of H-MEM, Zetaris, NVIDIA models or other third-party dependencies.

## Data and scope disclosure

The supplied practice-directory and waiting-time tables are SAMPLE data, not live appointment availability or measured patient outcomes. Optional web practice facts carry source URLs and must be distinguished from those seed tables. The rules source includes legal references, but the prototype is not medical advice or a substitute for professional guidance. It recommends appointment-navigation routes supported by the supplied data; it does not diagnose, book appointments or guarantee access.

## Public source repository

https://github.com/AndiKrue/fasttrack-termin

## Implementation references

- [Agent loop and verifier](../fasttrack/agent.py)
- [Zetaris JDBC and local source selection](../fasttrack/sources.py)
- [Zetaris registration](../zetaris/register.py)
- [Memory adapter](../fasttrack/memory.py)
- [H-MEM bridge](../meterless/bridge.ts)
- [Nemotron roles and call records](../fasttrack/llm.py)
- [Third-party H-MEM licence](../meterless/hmem/LICENSE)
