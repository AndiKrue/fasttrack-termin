# Sponsor technology: implementation and judge's guide

Track 02: **The Agent That Can Explain Why**. This explanation describes code on origin/main at `732a83b9b162f165af0643dabdeace6691b0742b`, not a claim that a live integration run succeeded. Source links pin that commit. Practices and waiting times in the seed FT_* tables are **SAMPLE data**. Web rows carry source URLs. This is not medical advice; in an emergency call **112**.

## The shared evidence loop

`fasttrack/agent.py::investigate` plans retrieval questions, assigns evidence IDs to query and optional web rows, recalls earlier findings, asks for an answer citing evidence IDs, filters nonexistent citations, verifies routes, and remembers only retained routes. The result exposes `routes`, `evidence`, `trace`, `model_calls`, `dropped` and `verifier_notes`; retained routes also carry `why_trace` entries with `eid`, `sql_or_query` and `url`.

SQL drafts for planned questions run concurrently with each other and optional web retrieval. Database queries still execute one by one on the single source connection. Trace query/web entries are emitted in processing order; their visible sequence does not imply sequential model execution. This change is implemented in commit [6e8e86d](https://github.com/AndiKrue/fasttrack-termin/commit/6e8e86d8958146a960e9373021c4467b88374fc8).

Sources: [fasttrack/agent.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/agent.py); [fasttrack/app.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/app.py) (`Handler.do_POST` streams completed steps through `/ask/stream` as NDJSON).

## Zetaris Lightning

**What it does here.** Lightning provides federated SQL over `FT_RULES.rules`, `FT_PRACTICES.practices` and `FT_WAITS.waits`: appointment-system rules, the sample directory and sample waiting observations. `zetaris/register.py::main` copies the seed CSVs into the platform driver container, creates Lightning databases and filestore tables, and reads back counts. `driver_container` locates that container. Registration uses DDL; the agent's retrieval path is separately restricted to a single read-only SELECT by `fasttrack/sources.py::check_sql`.

**Exact integration.** `ZetarisSource.__init__` connects through JayDeBeApi and `com.zetaris.lightning.jdbc.LightningDriver`. `ZetarisSource.query` executes guarded SQL and maps returned columns to row dictionaries. `open_source` selects the backend. `investigate` records each row under an evidence ID together with its SQL.

**Configuration.** `ZETARIS_JDBC_JAR` enables the Lightning path; `_jars` accepts a JAR path or directory. `ZETARIS_USER`, `ZETARIS_PASSWORD` and `ZETARIS_JDBC_URL` configure the connection. The source default is `jdbc:zetaris:lightning@localhost:10000`; Compose overrides it to `jdbc:zetaris:lightning@host.docker.internal:10000` and mounts JDBC files using `ZETARIS_JDBC_DIR`. Registration also reads `ZETARIS_PLATFORM` and `FT_CONTAINER_DIR`.

**Without it.** An empty/unset `ZETARIS_JDBC_JAR` selects `LocalSource`, an in-memory SQLite stand-in loaded from the same seed files and labelled `local-sqlite` in the trace. A failed configured JDBC connection is not silently converted into a local connection. Local results must not be presented as a successful Zetaris run.

**Where the judge sees it.** Confirm `trace.source = zetaris-lightning` in the response/run information. The timeline shows “Querying Zetaris (3 sources)”; open a route's “Why this route” and an evidence chip to inspect tables, SQL and rows. `sourceName` derives table labels from SQL FROM/JOIN clauses, even for the local stand-in, so that label alone does not prove Lightning executed the query. The trace's query step lists queries, evidence IDs and any errors. The registration console is an additional place to inspect actual counts, without scripting a count in advance.

Sources: [fasttrack/sources.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/sources.py); [zetaris/register.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/zetaris/register.py); [compose.yaml @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/compose.yaml); [fasttrack/static/app.js @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/app.js) (`sourceName`, `whyBlock`, `renderRoute`, `renderResult`).

## Meterless H-MEM

**What it does here.** After route verification, `investigate` passes a retained route, reason, question, timestamp, run ID and evidence bundle to the memory adapter. `HMemStore.remember` and `HMemStore.recall` call `_call`, which invokes the TypeScript bridge through tsx with JSON on stdin/stdout. In `meterless/bridge.ts`, the remember branch uses `HMEM.add`; recall uses `hmem.query`.

**Provenance boundary.** The current bridge persists route-and-reason text, a run tag and source `fasttrack:<run_id>`. It returns `hmem.ledger.history` action names when remembering. It does **not** copy the full question, timestamp or SQL evidence bundle into H-MEM. Recall returns item ID, content, source and relevance to the answer prompt. Full current evidence remains in the investigation response; memory is context and the new answer still undergoes citation filtering and verification. “Verified” means accepted by this model-based verifier, not independent clinical or legal validation.

**Configuration.** `FT_MEMORY` defaults to `hmem`; `FT_MEMORY=local` explicitly chooses JSONL. The bridge requires Node, its file and the tsx dependency installed under `meterless/node_modules/.bin`. `FT_HMEM_DIR` controls H-MEM persistence, defaulting to `runs/hmem`. Compose persists `runs` through its bind mount.

**Without it.** `open_memory` selects `LocalStore` if explicitly configured local or bridge initialization raises FileNotFoundError. This fallback writes `runs/memory.jsonl` and uses word matching for recall. It is labelled `local-jsonl`, not H-MEM. A bridge subprocess failure during recall/remember raises an error; the code does not silently fall back after such a runtime failure.

**Where the judge sees it.** Confirm `trace.memory = meterless-h-mem`. The timeline's “Recalling memory (Meterless H-MEM)” entry shows the actual recalled-record count; `trace.steps` contains that count. A second related question can demonstrate a hit only if its real count is nonzero. The trace does not expose the full recalled items or ledger. The bridge persists H-MEM state and ledger on disk; there is no dedicated ledger viewer in the UI. H-MEM is third-party, vendored unmodified under Apache-2.0; its licence is retained.

Sources: [fasttrack/memory.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/memory.py); [meterless/bridge.ts @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/meterless/bridge.ts); [meterless/hmem/LICENSE @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/meterless/hmem/LICENSE); [fasttrack/agent.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/agent.py); [compose.yaml @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/compose.yaml).

## NVIDIA Nemotron

**What it does here.** `fasttrack/llm.py::Nemotron.chat` calls the NVIDIA OpenAI-compatible chat-completions endpoint. `Nemotron.json` parses structured replies using `parse_json`. `MODELS` assigns defaults by role:

| Role | Model default | Use in the code |
| --- | --- | --- |
| planner | nvidia/nemotron-3.5-lightning-30b-a3b | Plan retrieval questions. |
| sql | nvidia/nemotron-3.5-lightning-30b-a3b | Draft SELECTs and the optional web search query. |
| verifier | nvidia/nemotron-3.5-lightning-30b-a3b | Extract stated web facts and check proposed routes against cited rows. |
| answer | nvidia/nemotron-3-ultra-550b-a55b | Synthesize and rank routes from current evidence and recalled context. |

**Configuration.** `NVIDIA_API_KEY` is required. `NVIDIA_BASE_URL` defaults to `https://integrate.api.nvidia.com/v1`. `FT_MODEL_PLANNER`, `FT_MODEL_SQL`, `FT_MODEL_VERIFIER` and `FT_MODEL_ANSWER` override role models. `FT_MODEL_FALLBACK` defaults to `nvidia/nemotron-3-ultra-550b-a55b`.

**Fallback.** Following a JSON/ValueError failure, `Nemotron.json` retries the role model with an instruction to output JSON immediately. If that also fails and the role model differs from the fallback, it makes one final attempt with `FT_MODEL_FALLBACK`. With the defaults, Lightning roles therefore escalate to Ultra after two JSON failures. A role already using the fallback does not get another model escalation. This is not a general fallback for missing credentials, HTTP errors or unavailable services. Without an API key, client construction fails; there is no automatic offline answer model. Commit [b398190](https://github.com/AndiKrue/fasttrack-termin/commit/b3981903241266cf35b0fa2fc9b77babf146c32b) adds this escalation.

**Where the judge sees it.** “Model calls” expands to Role, Model, Seconds and Tokens in/out. The result's `model_calls` records actual model names, including a fallback when used, elapsed time and API-reported usage. Console lines also report role/model/status/time. Do not invent token totals, claim measured efficiency gains, or assume the shared client's call list contains only the current question. “Removed by the verifier” appears when `dropped` is nonempty and shows a paired verifier note when available, otherwise the removal reason; unpaired notes remain separate. `why_trace` records each retained route's evidence references. These UI/result additions originate in [446aa57](https://github.com/AndiKrue/fasttrack-termin/commit/446aa574a5779520031efbbe9f61446aa77440d6).

**Why this is meaningful use.** Nemotron selects the information to retrieve, turns that plan into source queries, synthesizes an evidence-citing answer and performs the separate verification step before retained routes enter memory. Model roles and the escalation path are visible for inspection. This is an implementation description, not a benchmark or a guarantee that the verifier detects every unsupported statement.

Sources: [fasttrack/llm.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/llm.py); [fasttrack/agent.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/agent.py); [fasttrack/web.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/web.py); [fasttrack/static/app.js @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/app.js) (`renderResult`).

## Firecrawl: additional web evidence

**What it does here.** `fasttrack/web.py::web_evidence` asks the sql role for a German practice-search query, calls `FirecrawlSearch.search`, then asks the verifier role to extract facts stated on returned pages. The extraction prompt leaves missing fields null; a returned practice row is retained only if its URL belongs to the returned page set. This URL check does not independently prove every extracted fact is correct. `investigate` assigns web rows evidence IDs, stores their source URL and labels their query text as `web search: ...`, not executed SQL. The answer prompt prefers URL-backed rows over SAMPLE rows and asks it to identify sample facts.

**Configuration.** `FIRECRAWL_API_KEY` enables `open_search`. `FIRECRAWL_URL` overrides the default `https://api.firecrawl.dev/v1/search`, including for a self-hosted endpoint. The current adapter still requires a nonempty API-key setting when a custom endpoint is used. It makes at most one search request per enabled question; Nemotron generation retries are separate from that search request.

**Without it.** With no key, `open_search` returns None and the agent uses SQL evidence and memory without web retrieval. If configured search or extraction fails, the agent records a web-step error and continues. An empty page list supplies no web evidence. No fallback invents practice facts or appointment availability.

**Exclusions.** `EXCLUDED` contains doctolib, jameda, docinsider and sanego domain fragments. `FirecrawlSearch.search` adds site exclusions and drops returned URLs containing those fragments. This is the concrete exclusion logic, not a general determination of every website's terms.

**Where the judge sees it.** `trace.web = firecrawl-search` identifies configured search; check the web step for success, actual practice count or error, since the backend label alone does not prove retrieval succeeded. “Searching the web (Firecrawl)” shows the step. Web evidence chips are marked web; “Why this route” identifies the web host and links the URL. Phone and map actions appear only when cited rows contain those fields. Web evidence is distinct from SAMPLE FT_* data and is not proof of appointment availability.

Sources: [fasttrack/web.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/web.py); [fasttrack/agent.py @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/agent.py); [fasttrack/static/app.js @ 732a83b](https://github.com/AndiKrue/fasttrack-termin/blob/732a83b9b162f165af0643dabdeace6691b0742b/fasttrack/static/app.js) (`sourceName`, `whyBlock`, `renderRoute`).

## What the judge can inspect in one answer

Open “Why this route” for the evidence ID, table/web host, selected row fields and SQL or URL. `factLine` limits this compact view to selected fields; open the evidence chip for the full returned row. Expand “Model calls” and the trace, and inspect any “Removed by the verifier” section. Inspect the actual backend labels before attributing a run to a sponsor. Never expose .env, tokens, API keys or credential-bearing headers.

This display explains the route's cited inputs. It is not a deterministic sentence-by-sentence proof or a clinical validation. The current H-MEM ledger preserves memory activity and run provenance, not full SQL-row history.
