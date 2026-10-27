# Open Agent Hackathon 2026: submission texts

Each section below is ready to paste into the corresponding form field. Model names describe the defaults in the code; runtime overrides must be disclosed if used.

## Project name

FastTrack Termin

## Track

Track 02: The Agent That Can Explain Why

## Short description

FastTrack Termin helps statutory-insurance patients in Berlin identify the fastest supported route to a specialist appointment through a web UI, Telegram bot or Telegram mini app. It combines federated SQL and URL-backed web evidence, explains routes with inspectable rows, checks the draft with a separate verifier, and recalls earlier verified findings through Meterless H-MEM. Seed practices and waiting times are SAMPLE data. This is not medical advice.

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

An optional Firecrawl path in fasttrack/web.py makes one search per question when enabled. It uses api.firecrawl.dev with FIRECRAWL_API_KEY, or an endpoint configured through FIRECRAWL_URL for self-hosting. Nemotron Lightning forms the search query and is instructed to extract only facts stated on the returned pages, leaving absent fields null. Extracted rows are retained only when their source URL matches a returned page; the UI links that URL. The query excludes doctolib, jameda, docinsider and sanego, and matching URLs are filtered from results. The answer is instructed to prefer URL-backed web rows over SAMPLE rows and identify sample facts. These web rows are distinct from the SAMPLE seed tables and do not establish live appointment availability.

## How patients use it: web, Telegram and mini app

The web UI shows a live step timeline from /ask/stream, an NDJSON stream of completed agent steps followed by the result. Route cards show a reason and expected days when supplied. Evidence chips reveal the SQL and returned row; web evidence links its source. Call links and OpenStreetMap/Google route buttons appear when a cited row provides a phone number or address. Optional “Use my location” enables distance estimates, geocoding practice addresses through Nominatim; this is not a travel-time or appointment guarantee.

Telegram onboarding starts by scanning a QR code for https://t.me/FastTrackTerminBot. After starting the bot, the patient asks in chat and watches one status message update as the investigation progresses. Results include route reasons and, where supported by cited rows, phone details, map links and source links. “Open FastTrack app” opens /miniapp inside Telegram; the mini app uses Telegram theme colours and its main button for the same streamed investigation flow. The bot can discover the public tunnel hostname through cloudflared metrics and set its mini app menu button itself. It also accepts an explicit FT_MINIAPP_URL.

## Running the submission

Copy .env.example to .env, fill the required keys locally, then run:

```sh
docker compose up --build -d
```

The .env file is git-ignored and must never be committed. Compose starts app (the local web UI at http://127.0.0.1:8765), tunnel (a Cloudflare quick tunnel providing public HTTPS) and bot (Telegram @FastTrackTerminBot). The shared application image includes Python 3.12, JRE 17 for Zetaris JDBC and Node for the Meterless H-MEM bridge. In Compose, Zetaris is reached at host.docker.internal:10000; an empty ZETARIS_JDBC_JAR selects the labelled local SQLite stand-in rather than the real Zetaris integration.

For QR onboarding, run in a configured Python environment:

```sh
python -m fasttrack.telegram_bot --qr bot-qr.png
```

This obtains the configured bot's username from Telegram and writes its onboarding QR. For the submission bot, the destination is https://t.me/FastTrackTerminBot. Keep keys, tokens and credential-bearing headers out of recordings; the environment loader prints no values and the Telegram client redacts its token from error messages.

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

Nemotron drives the complete reasoning loop, including the check on its own proposed answer. Lightning 30B plans the information needed, translates each retrieval question into SQL over the federated schema, forms the optional Firecrawl search query, extracts page facts and later acts as the separate route verifier. Ultra 550B receives the patient's question, current evidence rows and recalled findings to rank routes and write their reasons with evidence IDs. This role allocation reserves Ultra for the evidence-synthesis step while giving Lightning explicit planning, retrieval and checking responsibilities. Crucially, generation does not end the workflow: the application filters invalid citations and only releases routes retained by the verifier with supporting evidence references. The same retained routes become future memory. The web UI, Telegram status message and mini app expose progress through that workflow. Per-role model selection and call records make this design inspectable, without claiming unmeasured speed, cost or accuracy gains.

## What is unique about our use of sponsor technology?

The sponsor integrations form one evidence loop. Zetaris provides the queryable facts across three logical sources. Nemotron decides what to retrieve, generates SQL, explains the resulting options and checks its draft. Meterless H-MEM retains accepted route explanations with run provenance and a ledger, then recalls them for the next question.

The useful distinction is the link between explanation and retrieval: a route's “why” comes with supporting SQL rows or URL-backed web rows. Memory helps continuity, while the next answer must still cite fresh evidence and pass verification. The current H-MEM bridge stores route text and run provenance rather than the full evidence bundle. Source and memory backend labels make the real integrations distinguishable from local fallbacks.

## Cursor use

Cursor was not used.

## Pre-existing components and attribution

No pre-existing components of our own were reused. Meterless H-MEM is a third-party component vendored unmodified in meterless/hmem under Apache-2.0; its licence is retained there. FastTrack Termin's application and integration code is provided in this public AGPL-3.0 repository. We do not claim authorship of H-MEM, Zetaris, NVIDIA models or other third-party dependencies.

## Data and scope disclosure

The supplied practice-directory and waiting-time tables are SAMPLE data, not live appointment availability or measured patient outcomes. Optional web practice facts carry source URLs and must be distinguished from those seed tables. The rules source includes legal references, but the prototype is not medical advice or a substitute for professional guidance. It recommends appointment-navigation routes supported by the supplied data; it does not diagnose, book appointments or guarantee access. Web, bot and mini app display emergency guidance: call 112 in an emergency.

## Public source repository

https://github.com/AndiKrue/fasttrack-termin

## Implementation references

- [Sponsor technology: files, configuration, fallbacks and judge inspection](SPONSORS.md)
- [Agent loop and verifier](../fasttrack/agent.py)
- [Zetaris JDBC and local source selection](../fasttrack/sources.py)
- [Zetaris registration](../zetaris/register.py)
- [Memory adapter](../fasttrack/memory.py)
- [H-MEM bridge](../meterless/bridge.ts)
- [Nemotron roles and call records](../fasttrack/llm.py)
- [Streaming endpoint](../fasttrack/app.py)
- [Web UI](../fasttrack/static/app.js)
- [Telegram bot and QR onboarding](../fasttrack/telegram_bot.py)
- [Telegram mini app](../fasttrack/static/miniapp.html)
- [Live web evidence](../fasttrack/web.py)
- [Compose services](../compose.yaml)
- [Application image](../Dockerfile)
- [Third-party H-MEM licence](../meterless/hmem/LICENSE)
