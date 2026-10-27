# FastTrack Termin: three-minute demo

## Edit and recording plan

Final runtime: **3:00**. The 60-second live-flow slot now covers web, Telegram QR onboarding, chat status and opening the mini app. Preserve the requested 20-second console shot as an inset over that slot's last 20 seconds; all other original shot durations stay unchanged.

Times are edit positions, not inference-time promises. Capture actual runs. If processing takes longer, cut the wait and display “Processing wait shortened”. Never fabricate route text, latency, call counts, verifier rejections or recall hits. Do not imply that different questions or clients share the same run ID.

Keep this exact editorial disclosure visible throughout:

> FT_* practices and waiting times are SAMPLE data. Web rows link their source. Not medical advice. Emergencies: 112.

## Before recording

- Pull the current main branch. Copy .env.example to .env and fill keys locally. Keep .env git-ignored and never commit or display it. Start the configured stack with `docker compose up --build -d`; build output reports stages. For recording, the services must already be ready.
- Compose services are app (http://127.0.0.1:8765), tunnel (Cloudflare quick tunnel with public HTTPS) and bot (Telegram @FastTrackTerminBot). The application image contains Python 3.12, JRE 17 for JDBC and Node for H-MEM. Zetaris is reached at host.docker.internal:10000; an empty ZETARIS_JDBC_JAR selects local SQLite.
- Use real Zetaris and H-MEM for sponsor shots. Confirm source = zetaris-lightning and memory = meterless-h-mem in the run information. A local fallback is not a demonstration of either sponsor integration.
- Generate the onboarding QR in a configured Python environment with `python -m fasttrack.telegram_bot --qr bot-qr.png`. Verify it resolves to https://t.me/FastTrackTerminBot. The command uses the configured bot's actual username, not a hard-coded destination. Do not commit generated QR files as part of this documentation change.
- Confirm the bot's “Open FastTrack app” button or “FastTrack” menu opens the current tunnel's /miniapp. The bot discovers the tunnel hostname through cloudflared metrics and sets its mini app menu itself; FT_MINIAPP_URL is an explicit override. If the hostname is not ready, rehearse after setup completes rather than depicting a missing button as working.
- Enable optional Firecrawl only with valid local configuration: FIRECRAWL_API_KEY for the cloud endpoint or FIRECRAWL_URL for the configured self-hosted endpoint. Its query excludes doctolib, jameda, docinsider and sanego, and matching URLs are filtered. Lightning is instructed to extract only stated page facts and the answer prefers URL-backed web rows over SAMPLE rows. Show actual source rows; do not claim that source URLs prove live appointment availability.
- Rehearse supported first and second questions. A genuine recall count is visible in the web timeline and trace. Use the same persistent H-MEM store; a missing recall must not be edited into a hit.
- Prepare the Zetaris SQL editor, selected application console lines, and real web/Telegram captures. Keep tokens, API keys, request headers, environment dumps and private patient information out of frame. Do not open an actual call during the demo.

## Shot list and exact narration

### 00:00–00:20 | Problem | 20 seconds

**Picture:** Title card, then the web question box. Show the run command as an editorial caption, not a simulated successful deployment.

**Exact on-screen text:**

> FastTrack Termin
>
> Which route to a specialist appointment, and why?
>
> Berlin · Statutory insurance
>
> Run: docker compose up --build -d

**Narration:**

> “A statutory-insurance patient in Berlin needs a specialist, but rules, practice details and waiting observations are scattered. FastTrack Termin explains a supported route through web, Telegram or a mini app. The seed practices and waiting times are sample data. This is not medical advice.”

### 00:20–01:20 | Live flow: web, Telegram and mini app | 60 seconds

#### 00:20–00:40 | Web question and streaming timeline

**Picture:** Open http://127.0.0.1:8765. Submit the existing question with “Find the fastest route”. Show the real timeline updating through /ask/stream (NDJSON). Steps report completed work, not a percentage of inference progress.

**Exact question:**

> I live in Köpenick, have knee pain for three weeks and a referral from my GP without urgency code. How do I get an orthopaedics appointment fastest?

**Existing timeline labels to capture:**

- Planning with Nemotron
- Querying Zetaris (3 sources)
- Searching the web (Firecrawl)
- Recalling memory (Meterless H-MEM)
- Verifying every claim

Optional web search may be skipped; do not imply it ran when disabled.

**Narration:**

> “We ask about orthopaedics in Köpenick with a referral but no urgency code. The live timeline reports planning, source retrieval, optional web evidence, memory recall and verification. Each update comes from the running investigation.”

#### 00:40–01:00 | Scan QR, ask in Telegram, watch status

**Picture:** Scan the real onboarding QR. Open @FastTrackTerminBot and press Telegram's Start control if needed. Send the same question. Show one message being edited as steps finish, followed by the actual route response. Shorten processing waits transparently.

**Exact editorial caption:**

> Scan → ask → watch one live status message

**Existing bot text and labels to capture:**

- Working on your question
- Planning (Nemotron)
- Querying Zetaris
- Web search (Firecrawl)
- Memory (H-MEM)
- Verifying

Keep generated step counts and returned route text as recorded.

**Narration:**

> “Scan the QR to open the Telegram bot and ask in chat. One status message updates as work completes. The answer includes reasons, plus phone details, map and source links when its cited evidence provides them.”

#### 01:00–01:20 | Open mini app, with console inset

**Picture:** Tap the bot's “Open FastTrack app” button or “FastTrack” menu. Show /miniapp inside Telegram with its theme colours, question field and Telegram main button. The console inset occupies this same interval; it is not an additional 20-second shot.

**Existing mini app main-button text:**

> Find fastest route

**Exact editorial captions:**

> Same agent flow inside Telegram
>
> Nemotron by role: Lightning 30B plans, retrieves and verifies; Ultra 550B answers

**Console capture:** Show real application lines beginning with [nemotron], with the actual planner, sql, answer and verifier model names. Defaults are nvidia/nemotron-3.5-lightning-30b-a3b and nvidia/nemotron-3-ultra-550b-a55b. Never invent HTTP statuses or elapsed times. These lines print after requests return; they are not heartbeats. Optional web-query and extraction calls reuse the sql and verifier roles.

**Narration:**

> “Open the mini app inside Telegram, using its theme and main button. The inset shows actual Nemotron calls: Lightning plans, retrieves and verifies; Ultra answers. The recorded role, model, status and elapsed time make that allocation inspectable.”

### 01:20–02:00 | Routes, reasons, evidence and actions | 40 seconds

**Picture:** Return to the completed web run. Show a route card, its reason and expected days if returned. Click an actual evidence chip to reveal the SQL and row. For a web row, open its chip and point to “Open source”. Do not label a web-search description as executed SQL.

When an actual cited row has phone/address, highlight “Call ” followed by the returned phone number, “Route (OSM)” and “Route (Google)”. Show the optional “Use my location” control without requiring location permission for the recording. If used, describe the Nominatim-based output as a distance estimate, not journey time. If fields are absent, omit the corresponding action close-up.

**Exact editorial captions:**

> Why this route?
>
> Evidence chip → query or web search → actual row
>
> Call and route actions come from cited phone/address fields

The current web card renders the reason without a literal “Why:” prefix. Telegram and mini app use “Why:”. Use generated content exactly as returned; do not add a fabricated recommendation or expected-day value.

**Narration:**

> “Each card shows the route and its reason. An evidence chip opens the supporting query and row, or a web result with its source link. When cited data provides a phone or address, the card offers call and map actions. Location sharing can add a distance estimate. Sample waiting observations are not live availability. The verifier checks the draft against cited rows; that is a model-based check, not a medical or legal guarantee.”

### 02:00–02:20 | Zetaris query | 20 seconds

**Picture:** Execute this inspection query in the Zetaris SQL editor. Show actual output and its SAMPLE markers. This is an inspection query, not a claim about the exact SQL generated by the agent.

```sql
SELECT p.practice_id, p.name, p.sample AS practice_data,
       w.channel, w.days_to_appointment, w.sample AS wait_data
FROM FT_PRACTICES.practices p
JOIN FT_WAITS.waits w ON p.practice_id = w.practice_id
WHERE p.specialty = 'orthopaedics'
ORDER BY w.days_to_appointment
```

**Exact editorial caption:**

> Zetaris Lightning: FT_RULES.rules · FT_PRACTICES.practices · FT_WAITS.waits
>
> Inspection query: practices joined to waiting observations

**Narration:**

> “In Zetaris, this inspection query joins practices to waiting observations and shows the sample markers. The agent uses Lightning JDBC over these sources and the separate rules table. Backend labels distinguish the real integration from the local SQLite stand-in.”

### 02:20–02:40 | H-MEM recall on a second question | 20 seconds

**Picture:** In the mini app or web UI, submit the related question below. Show the actual “Memory (H-MEM)” or “Recalling memory (Meterless H-MEM)” timeline update and its real count. In the web UI, “Trace: every step, query and verifier note” also exposes the recall entry. If inspecting the stream response, the final result is under result; recall is in result.trace.steps.

**Exact question:**

> For the same orthopaedics question in Köpenick, explain again why the recommended route fits my referral without an urgency code.

**Exact editorial captions:**

> Recall earlier verified findings
>
> H-MEM: route + reason + run provenance + ledger
>
> The new answer still needs current evidence

**Narration:**

> “The first answer's retained routes entered H-MEM with their reasons and run provenance, backed by its ledger. This related question shows the actual recall count in the timeline. Memory provides context; the new answer still needs current evidence and verification.”

**Recording condition:** Claim a hit only if the actual recall count is nonzero. The current bridge stores route text and run provenance, not the full SQL evidence payload. H-MEM's persisted ledger is not rendered in a dedicated UI viewer.

### 02:40–03:00 | Close | 20 seconds

**Picture:** Finish on the mini app and a web evidence chip, then the repository URL.

**Exact closing card:**

> FastTrack Termin
>
> Track 02: The Agent That Can Explain Why
>
> Web · Telegram @FastTrackTerminBot · Mini app
>
> Zetaris · Meterless H-MEM · NVIDIA Nemotron
>
> github.com/AndiKrue/fasttrack-termin

Retain the SAMPLE/not-medical-advice/emergency disclosure through the final frame.

**Narration:**

> “Web, Telegram and mini app use the same investigation flow. Zetaris supplies queryable facts, Firecrawl adds source-linked practice evidence, Nemotron proposes and checks routes, and Meterless H-MEM carries retained findings forward. The reasons remain inspectable, with sample-data limits visible. In an emergency, call 112.”

## Evidence boundaries

The web UI now renders streamed steps, recall counts and a trace disclosure; the previous static-only recording instructions no longer apply. Show verifier drops only when the captured trace reports them. Model calls may accumulate in a shared client, so do not describe the footer count as per-question without checking logs. Keep secrets out of every capture; do not display .env, bot API URLs containing tokens or credential-bearing request headers. No live deployment, response or recall success is asserted by this shot list.

Implementation references: [streaming endpoint](../fasttrack/app.py), [web UI](../fasttrack/static/app.js), [Telegram bot](../fasttrack/telegram_bot.py), [mini app](../fasttrack/static/miniapp.html), [agent loop](../fasttrack/agent.py), [model calls](../fasttrack/llm.py), [web evidence](../fasttrack/web.py), [H-MEM bridge](../meterless/bridge.ts), [Compose](../compose.yaml), [image](../Dockerfile).
