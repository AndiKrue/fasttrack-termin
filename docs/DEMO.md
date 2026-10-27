# FastTrack Termin: three-minute demo

## Edit and recording plan

Final runtime: **3:00**. The requested individual shots total 3:20. Preserve all their durations by placing the 20-second Nemotron console shot as an inset over the last 20 seconds of the 60-second live-question shot.

Times below are edit positions, not promised inference times. Capture actual runs; if processing takes longer, cut the wait and display “Processing wait shortened”. Never fabricate a result, latency, call count, verifier rejection or memory hit.

Keep this exact editorial disclosure visible throughout:

> SAMPLE practices and waiting times. Not medical advice.

## Before recording

- Use the actual Zetaris platform and registered seed tables. Confirm the first response's trace says source = zetaris-lightning.
- Install the Meterless bridge dependencies and use H-MEM. Confirm memory = meterless-h-mem. Local fallback runs do not demonstrate sponsor integrations.
- For this SQL-focused shot list, leave optional Firecrawl search disabled and confirm the UI footer shows web off. If recording with web search enabled instead, distinguish URL-backed web rows from SQL evidence and SAMPLE seed rows in the narration.
- Keep the NVIDIA models at the documented defaults, or identify the actual overrides on screen.
- Rehearse until the first question returns a supported route and a related second question produces an actual recall. The recall count is in the second response's trace.steps entry with step = recall. The UI footer shows the backend, not the recall count.
- Prepare the browser Network panel to inspect the second /ask JSON response. Prepare the Zetaris SQL editor and the application console.
- Show only application log lines and selected response fields. Keep credentials, request headers, environment dumps and private patient information out of frame.
- Do not turn a SAMPLE waiting-time observation into a promise of an appointment. No timing or outcome figures are scripted below.

## Shot list and exact narration

### 00:00–00:20 | Problem | 20 seconds

**Picture:** Title card, then the application's question box.

**Exact on-screen title:**

> FastTrack Termin  
> Which route to a specialist appointment, and why?

**Exact supporting text:**

> Berlin · Statutory insurance  
> Rules + practices + waiting-time observations  
> SAMPLE practices and waiting times. Not medical advice.

**Narration:**

> “For a statutory-insurance patient in Berlin, finding a specialist means piecing together rules, practice information and waiting-time observations. FastTrack Termin proposes a route and shows the evidence behind its reason. This prototype uses sample practices and waiting times. It is not medical advice.”

### 00:20–01:20 | Live question in the UI | 60 seconds

**Picture:** Open http://127.0.0.1:8765. Show the existing question, click the existing button and capture the real response. During 01:00–01:20, retain the UI as the main picture and add the console inset described below.

**Exact question, matching the UI default:**

> I live in Köpenick, have knee pain for three weeks and a referral from my GP without urgency code. How do I get an orthopaedics appointment fastest?

**Existing button text:**

> Find the fastest route

**Existing processing text:**

> Planning, querying the sources, verifying ...

**Editorial captions, in order:**

> Plan the facts needed  
> Query the sources  
> Recall earlier verified findings  
> Draft, then verify

**Narration, 00:20–01:00, with room for the interaction:**

> “Here is the patient's question: they live in Köpenick and want an orthopaedics appointment, with a referral but no urgency code. The planner chooses which facts to retrieve. The SQL role queries the sources. The answer receives those rows and earlier verified findings, then a separate verifier checks the draft. Only retained routes with evidence references reach this screen. Processing time is shown as recorded, or explicitly shortened in the edit.”

### 01:00–01:20 | Nemotron console inset | 20 seconds, overlapping the live shot

**Picture:** Enlarge real application log lines containing the literal prefix [nemotron]. Show the actual planner, sql, answer and verifier role/model strings. Retain the UI behind the inset.

**Exact editorial caption:**

> Nemotron by role  
> Lightning 30B: planner · SQL · verifier  
> Ultra 550B: answer

**Actual code-default model strings to capture:**

- nvidia/nemotron-3.5-lightning-30b-a3b
- nvidia/nemotron-3-ultra-550b-a55b

The remaining status codes and elapsed times must come from the run. Do not paste invented log lines. These lines print after each HTTP request returns; they are not progress heartbeats.

**Narration:**

> “These are the actual Nemotron calls. Lightning handles planning, SQL and verification; Ultra writes the evidence-based answer. The console reports each role, model, HTTP status and elapsed time. This is role-specific orchestration, with a separate checking step before routes are returned.”

### 01:20–02:00 | Routes, “Why” and evidence rows | 40 seconds

**Picture:** Scroll through a real retained route. Zoom on its “Why:” paragraph, then the evidence block beneath it. Keep the SAMPLE disclosure visible. Do not script the generated route text.

**Exact editorial captions:**

> Why this route?  
> Evidence ID → executed SQL → returned row  
> Only routes retained by the verifier are shown

**Existing UI label to highlight:**

> Why:

Show the actual evidence ID, SQL and row rendered by the UI. Highlight sample = SAMPLE in a returned practice or waiting-time row if present. If the model's SELECT omitted that column, keep the editorial SAMPLE disclosure and show the marker in the next SQL-editor shot.

**Narration:**

> “The route comes with a reason. Below it is the evidence ID, the query that produced the evidence, and the returned row. We can inspect the basis of the recommendation rather than accepting an explanation on trust. Practice and waiting-time observations here are sample data, not live availability. The verifier checks draft routes against their cited rows; the application also removes invalid evidence IDs. This is a model-based check, not a clinical or legal guarantee.”

### 02:00–02:20 | Query in the Zetaris UI | 20 seconds

**Picture:** Run this read-only query in the Zetaris SQL editor and show its actual output. This is an explicit inspection query; do not label it as agent-generated SQL unless the captured agent actually generated it.

**Exact query text:**

```sql
SELECT p.practice_id, p.name, p.sample AS practice_data,
       w.channel, w.days_to_appointment, w.sample AS wait_data
FROM FT_PRACTICES.practices p
JOIN FT_WAITS.waits w ON p.practice_id = w.practice_id
WHERE p.specialty = 'orthopaedics'
ORDER BY w.days_to_appointment
```

**Exact editorial captions:**

> Zetaris Lightning: inspect the federated data  
> FT_RULES.rules · FT_PRACTICES.practices · FT_WAITS.waits  
> Inspection query: practices joined to waiting-time observations

**Narration:**

> “Here is the data in Zetaris itself. This inspection query joins the practice and waiting-time sources and exposes their sample markers. The agent uses Lightning JDBC over these sources and the separate rules table. The trace identifies the actual backend used.”

### 02:20–02:40 | H-MEM recall on a second question | 20 seconds

**Picture:** Submit the exact related question below in the UI. Cut any wait transparently. Show the second /ask response's trace: memory = meterless-h-mem and the recall entry's actual records value. Use the browser Network response view; the current page does not render a memory-detail panel.

**Exact second question:**

> For the same orthopaedics question in Köpenick, explain again why the recommended route fits my referral without an urgency code.

**Exact editorial captions:**

> Second question: recall earlier verified findings  
> H-MEM: route + reason + run provenance + ledger  
> Current answer still needs fresh evidence

**Narration:**

> “The first answer's retained routes entered H-MEM with their reasons and run provenance, backed by its ledger. On this related question, the trace shows the actual recall count. Earlier findings provide context, while the new answer still needs current evidence and verification.”

**Recording condition:** Show a nonzero recall count only when the actual response reports it. If no findings are recalled, rehearse a supported related question; do not claim a hit. H-MEM currently stores route text and run provenance, not the full SQL evidence payload. The ledger is persisted under runs/hmem by default; the UI does not display it.

### 02:40–03:00 | Close | 20 seconds

**Picture:** Return to a retained route and its evidence, then end on the repository URL.

**Exact closing card:**

> FastTrack Termin  
> Track 02: The Agent That Can Explain Why  
> Zetaris · Meterless H-MEM · NVIDIA Nemotron  
> github.com/AndiKrue/fasttrack-termin  
> SAMPLE practices and waiting times. Not medical advice.

**Narration:**

> “FastTrack Termin connects retrieval, explanation, verification and memory. Zetaris supplies the queryable facts, Nemotron plans and checks the reasoning workflow, and Meterless H-MEM carries accepted findings into the next question. The result is an appointment-navigation prototype whose reasons can be inspected, with its sample-data limits kept visible.”

## Evidence boundaries for the recording

The existing UI shows route reasons, SQL evidence, optional web source links, caveats and a run/backend/call-count footer. It does not show a verifier review panel, a memory explorer or a ledger viewer. Use actual response JSON or the persisted H-MEM files for those details. Do not imply that a verifier dropped a route unless the captured trace records it. Model calls can accumulate in the shared client; do not narrate the footer as a per-question call count without checking the trace and logs.

Implementation references: [UI](../fasttrack/app.py), [agent loop](../fasttrack/agent.py), [model logging](../fasttrack/llm.py), [sources](../fasttrack/sources.py), [memory adapter](../fasttrack/memory.py), [H-MEM bridge](../meterless/bridge.ts).
