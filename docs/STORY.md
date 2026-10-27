# From another phone call to a reason you can check

Track 02: “The Agent That Can Explain Why”. This is the patient-first story for FastTrack Termin and the opening of the [slide deck](deck/deck.md).

## Open with the feeling

> Weeks of calling. Still no appointment. And no clear reason why.
>
> You need a specialist in Berlin. You have a referral, but you do not know which route to try next. Another list of practices leaves you with the same question: why would this option work for me?

This is an **illustrative pitch scenario**, not a patient testimonial, a finding from the code, or a waiting-time statistic. It frames the problem requested for the presentation. No prevalence, average wait, time saved or success rate is asserted. The app’s example question supplies a Berlin district, a specialist need and a referral situation; it does not establish a history of unsuccessful calls. See [`fasttrack/static/index.html`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/index.html), at source snapshot `732a83b9b162f165af0643dabdeace6691b0742b`.

## Make the turn concrete

> Now there is a route with a reason. Open “Why this route”: see the cited fact, where it came from, and the SQL or source page behind it. You can check the basis for the recommendation before deciding what to do next.

The product change is an inspectable recommendation. It is not a booked appointment or a guarantee of faster access. The code ranks routes from available evidence; seed practices and waiting times are SAMPLE data. The answer prompt forbids medical advice and directs emergencies to 112. [`fasttrack/agent.py`, `ANSWER` and `investigate`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/agent.py).

## Show the reason, then the boundary

| Story beat | What a judge can inspect | Code evidence |
| --- | --- | --- |
| “Why this route?” | A line per cited evidence row: its ID, source label, selected row fields, and SQL or URL. The source label is derived from SQL tables or the web host. | [`fasttrack/static/app.js`: `sourceName`, `factLine`, `whyBlock`](https://github.com/AndiKrue/fasttrack-termin/blob/446aa574a5779520031efbbe9f61446aa77440d6/fasttrack/static/app.js), commit `446aa574a5779520031efbbe9f61446aa77440d6`. |
| “What was left out?” | “Removed by the verifier” shows rejected routes with a paired verifier note when available, otherwise a reason; unpaired notes can appear separately. | [`fasttrack/agent.py`: `investigate`](https://github.com/AndiKrue/fasttrack-termin/blob/446aa574a5779520031efbbe9f61446aa77440d6/fasttrack/agent.py) returns `dropped`, `verifier_notes` and per-route `why_trace`; [`fasttrack/static/app.js`](https://github.com/AndiKrue/fasttrack-termin/blob/446aa574a5779520031efbbe9f61446aa77440d6/fasttrack/static/app.js) renders the list. Commit `446aa574a5779520031efbbe9f61446aa77440d6`. |
| “What did the models do?” | “Model calls” exposes role, model, seconds and input/output tokens when returned. This is run telemetry, not a benchmark result. | [`fasttrack/static/app.js`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/app.js) and [`fasttrack/llm.py`: `Nemotron.chat`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/llm.py), snapshot `732a83b9b162f165af0643dabdeace6691b0742b`. |

These views expose the recommendation’s supporting data and the verifier’s decision. They do not prove the sources are correct or that the LLM verifier cannot make a mistake. The UI’s “Zetaris” source label comes from the SQL; the run trace identifies the actual backend, including the local SQLite stand-in. [`fasttrack/static/app.js`: `sourceName`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/app.js), [`fasttrack/sources.py`: `open_source`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/sources.py), and [`fasttrack/agent.py`: `investigate`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/agent.py).

## Keep the technical explanation behind the patient story

The planner selects factual questions. SQL drafting for the planned questions overlaps with the optional web search; database queries execute one by one on the single connection. Evidence rows receive IDs, memory is recalled, the answer cites IDs, and the verifier filters routes before retained findings are remembered. This describes execution order, not measured acceleration. [`fasttrack/agent.py`: `investigate`](https://github.com/AndiKrue/fasttrack-termin/blob/6e8e86d8958146a960e9373021c4467b88374fc8/fasttrack/agent.py), commit `6e8e86d8958146a960e9373021c4467b88374fc8`.

Lightning is the default for planner, SQL and verifier; Ultra is the default for the answer. When a role returns no parseable JSON on both initial attempts and its configured model differs from the fallback, the code makes a final attempt with the configured fallback, Ultra by default. This handles JSON-format failure, not every API failure. [`fasttrack/llm.py`: `MODELS`, `FALLBACK`, `Nemotron.json`](https://github.com/AndiKrue/fasttrack-termin/blob/b3981903241266cf35b0fa2fc9b77babf146c32b/fasttrack/llm.py), commit `b3981903241266cf35b0fa2fc9b77babf146c32b`.

Memory also has a boundary: the H-MEM bridge retains route/reason text with run provenance; it does not persist the full SQL/row payload. [`meterless/bridge.ts`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/meterless/bridge.ts) and [`fasttrack/memory.py`](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/memory.py), snapshot `732a83b9b162f165af0643dabdeace6691b0742b`.

## Close on the patient’s next decision

> A route to consider. A reason to read. Evidence to check.

Keep SAMPLE labels visible in captures. Show a real returned route and its evidence, then a removed route only if the recorded run contains one. Do not stage a successful booking or invent a verifier rejection. This document describes code on `origin/main`; it does not report a new live run.
