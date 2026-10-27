# FastTrack Termin: narrated demo shot list

## Source and recording contract

The executable recording manifest is [AndiKrue/narrated: demo/fasttrack-termin-v1.yaml @ 021db6a](https://github.com/AndiKrue/narrated/blob/021db6a3cc9b8d102414f3af2279fff27e91d834/demo/fasttrack-termin-v1.yaml). This document follows its exact shot order:

`cold_open`, `ask`, `plan`, `web`, `memory`, `verify`, `results`, `why`, `refused`, `close`.

The manifest drives a live web run at http://127.0.0.1:8765/. Narration and actions come from that YAML; this document maps the shots to inspectable implementation facts. Target: the requested three-minute demo. The manifest does not define fixed per-shot durations, so use the rendered narration's actual timings rather than claiming a measured runtime here. It configures narration through a local Orpheus speech endpoint, voice tara, and SRT-only captions. No video render or live integration success is asserted by this document.

Application facts below are pinned to origin/main commit **732a83b9b162f165af0643dabdeace6691b0742b**. Key changes: [446aa57: explainability UI and result fields](https://github.com/AndiKrue/fasttrack-termin/commit/446aa574a5779520031efbbe9f61446aa77440d6), [6e8e86d: concurrent SQL drafting/web retrieval](https://github.com/AndiKrue/fasttrack-termin/commit/6e8e86d8958146a960e9373021c4467b88374fc8), [b398190: JSON fallback model](https://github.com/AndiKrue/fasttrack-termin/commit/b3981903241266cf35b0fa2fc9b77babf146c32b).

Keep the existing footer or this exact editorial disclosure readable:

> Practices and waiting times in the FT_* tables are SAMPLE data; web rows link their source. Not medical advice. Emergencies: 112.

## Shot list aligned to narrated

| Shot ID | Manifest action and exact on-screen target | Narration focus and factual boundary |
| --- | --- | --- |
| cold_open | Wait for `#go`; highlight `.hero h1`. Existing headline: “The fastest route to a specialist appointment in Berlin, with the reasons behind every step.” | Begin with the patient's uncertainty and repeated unsuccessful calls as a scripted vignette. Do not present the vignette as observed patient history, a sourced statistic or a measured waiting-time claim. |
| ask | Highlight `#q`, then click `#go` during the second narration sentence. Existing button: “Find the fastest route”. Use the exact question below. | A patient states their district, specialist need and referral details. This starts one real investigation; do not insert a fabricated answer. |
| plan | Wait for `#steps li`; highlight `#progress`. Existing labels include “Planning with Nemotron” and “Querying Zetaris (3 sources)”. | The planner selects retrieval questions. SQL drafts run concurrently; database queries execute sequentially on one JDBC connection across the rules, directory and waiting sources. Expected days are supplied-data estimates, not proven appointment access. |
| web | Highlight `#steps li[data-step=web]`, labelled “Searching the web (Firecrawl)”. | Web retrieval overlaps SQL drafting. Lightning is instructed to extract stated page facts; each retained web row has a URL from the returned page set. Excluded portal fragments are doctolib, jameda, docinsider and sanego. The URL check is not an independent factual guarantee. |
| memory | Highlight `#steps li[data-step=recall]`, labelled “Recalling memory (Meterless H-MEM)”. | Show the real recall count. H-MEM retains prior route/reason text and run provenance, not full SQL evidence. A zero count is valid; do not narrate a successful hit unless the actual run shows one. |
| verify | Highlight `#steps li[data-step=verify]`, labelled “Verifying every claim”. | The verifier is prompted to check proposed routes against their cited rows. The application keeps only selected routes with existing evidence references. This is model-based verification, not a guarantee that every unsupported statement is detected. |
| results | Wait for `article.route`, scroll to `#results`, highlight the actual route card. | Show ranked routes, reasons and expected days only when returned. Call and directions controls require a cited row with phone/address. Do not imply that a SAMPLE observation is live availability, or place an actual call for the recording. |
| why | Click `article.route details.whyof summary`; highlight `article.route details.whyof`. Exact label: “Why this route”. | Each cited row is shown with its evidence ID, SQL-derived table label or web host, selected row fields, and the SQL or URL. Evidence chips reveal full rows. This is an inspectable input trail, not a deterministic proof of each sentence. |
| refused | Scroll to `#runinfo`. The result region above contains “Removed by the verifier” when there are dropped routes and a collapsed “Model calls” disclosure when call records exist. | Show actual removals and notes, and the actual role/model/seconds/token records. The YAML only scrolls; it does not expand Model calls. Open it manually for an additional inspection capture if needed. Never manufacture a dropped route to match the narration. |
| close | Highlight `.foot` during the emergency-guidance sentence. | Name NVIDIA Nemotron, Zetaris, Meterless and Firecrawl; mention browser and Telegram. End with the visible SAMPLE disclosure and “Not medical advice. In an emergency call 112.” |

**Exact question in the current web UI:**

> I live in Köpenick, have knee pain for three weeks and a referral from my GP without urgency code. How do I get an orthopaedics appointment fastest?

**Existing action labels, conditional on cited fields:** “Call ” followed by the actual phone, “Route (OSM)”, “Route (Google)” and “Open source”. Optional “Use my location” geocodes practice addresses with Nominatim and calculates distance estimates; it does not estimate travel or appointment time.

The “Why this route” compact list selects row fields; click an evidence chip for the full row. Table labels are extracted from SQL FROM/JOIN clauses and also appear with the local stand-in. Confirm the run's actual source backend before calling a displayed table a successful Zetaris query.

## Model and verifier inspection for the refused shot

The response exposes `dropped`, `verifier_notes` and per-retained-route `why_trace`. The latter contains `eid`, `sql_or_query` and `url`; the UI builds its visible fact list from cited entries in `evidence`. A removal may show a paired verifier note, or a generic removal reason when no note is paired. If no route was dropped, say so or retain only the actual model-call inspection; the “Removed by the verifier” section is conditional.

Expand “Model calls” to see Role, Model, Seconds and Tokens in/out. Defaults are Lightning 30B for planner/sql/verifier, including web query/extraction, and Ultra 550B for answer. After two JSON failures, a role whose model differs from `FT_MODEL_FALLBACK` gets one final fallback-model attempt; the default fallback is Ultra. Show its actual model record only if that path ran. Do not interpret this as a retry guarantee for credentials or HTTP errors. Call records can accumulate on a shared client; do not invent a per-question total.

## Setup and live-take checks

- Copy .env.example to the git-ignored .env and fill keys locally; never commit or display credentials. Start the configured stack with `docker compose up --build -d` before recording. Services are app, Cloudflare quick tunnel and Telegram bot. Python 3.12, JRE 17 and Node are in the application image. Compose reaches Zetaris at host.docker.internal:10000; an empty ZETARIS_JDBC_JAR selects local SQLite.
- Confirm `trace.source = zetaris-lightning`, `trace.memory = meterless-h-mem` and a successful web step for the intended sponsor demonstration. A configured backend name does not prove a successful retrieval. Keep error cases visible or retake; do not relabel local fallbacks as sponsor executions.
- The narrated results shot waits for a real route card with its configured timeout. If the run outlasts the earlier narration, retake or adjust recording pacing in the narrated workflow. Do not claim the script's wait configuration is measured inference latency. Any shortened wait needs an explicit “Processing wait shortened” caption.
- Keep API keys, Telegram tokens, .env, credential-bearing request headers and private patient information out of captures. Show selected application logs or UI records, not environment dumps. No code changes or recording-manifest changes are part of this documentation task.
- The current YAML's emotional opening and absolute verification language are scripted narration, not evidence of real access delays or perfect verification. For a factual retake, describe uncertainty, SAMPLE observations and routes retained by the model verifier. This document does not silently rewrite the executable narration.

## Supplemental Telegram onboarding capture

The current narrated YAML records the browser; it mentions Telegram at close but contains no QR, chat or mini-app actions. Keep the following as a separately identified supplementary capture, not as unrecorded steps attributed to that live take:

1. Generate the real onboarding QR in a configured environment: `python -m fasttrack.telegram_bot --qr bot-qr.png`. It resolves the configured bot's username through Telegram; verify the submission destination is https://t.me/FastTrackTerminBot.
2. Scan the QR, start the bot and send the same question. Show “Working on your question” being edited as actual plan/query/web/recall/verify steps complete, then the real answer with supported phone, map and source details.
3. Tap “Open FastTrack app” or the “FastTrack” menu to open /miniapp. The bot discovers the quick-tunnel hostname through cloudflared metrics and sets its menu; FT_MINIAPP_URL is an override. Show Telegram theme colours and its “Find fastest route” main button.
4. If demonstrating a second-question memory hit, show the actual nonzero recall count. The primary narrated YAML has only one submitted question and does not itself demonstrate a second-question recall experiment.

Suggested exact supplementary caption: “Scan QR → ask in Telegram → watch live status → open mini app”. Keep SAMPLE, not-medical-advice and 112 guidance readable throughout. Do not imply that independent chat and web questions share a run ID.

## Implementation references

All application references are pinned to origin/main commit 732a83b9b162f165af0643dabdeace6691b0742b:

- [Agent loop, concurrency and result fields](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/agent.py)
- [UI fact lines, removals and model calls](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/app.js)
- [Headline, question and footer](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/index.html)
- [Nemotron roles and JSON fallback](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/llm.py)
- [Firecrawl adapter](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/web.py)
- [H-MEM adapter](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/memory.py) and [bridge](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/meterless/bridge.ts)
- [Telegram QR, status and menu](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/telegram_bot.py) and [mini app](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/miniapp.html)
- [Compose](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/compose.yaml) and [image](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/Dockerfile)

[Sponsor implementation, configuration, fallback and inspection guide](SPONSORS.md).
