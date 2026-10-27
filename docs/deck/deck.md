---
marp: true
theme: default
size: 16:9
paginate: true
title: FastTrack Termin | The Agent That Can Explain Why
description: Open Agent Hackathon 2026, Track 02 and NVIDIA Nemotron prize
footer: 'FastTrack Termin · Hackathon prototype · SAMPLE seed data · Not medical advice'
style: |
  section { background: #f8fafb; color: #142c3a; font-family: Arial, sans-serif; font-size: 27px; padding: 54px 64px 64px; line-height: 1.35; }
  h1 { font-size: 47px; line-height: 1.12; letter-spacing: -1.1px; margin-bottom: 28px; color: #142c3a; }
  h2 { font-size: 29px; color: #087c83; margin: 0 0 14px; }
  strong { color: #087c83; }
  p { margin: 12px 0; }
  ul { padding-left: 26px; }
  li { margin: 12px 0; }
  footer { font-size: 13px; color: #536975; left: 64px; bottom: 23px; }
  section::after { font-size: 14px; color: #536975; }
  section.title { background: #142c3a; color: #f8fafb; }
  section.title h1 { color: #fff; font-size: 78px; margin: 24px 0; }
  section.title strong { color: #6ed5cd; }
  section.title footer { color: #c3d5dc; }
  .eyebrow { text-transform: uppercase; letter-spacing: 2px; color: #087c83; font-size: 18px; margin-bottom: 18px; }
  .title .eyebrow { color: #6ed5cd; }
  .lead { font-size: 35px; line-height: 1.3; max-width: 1000px; }
  .small { font-size: 20px; color: #536975; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 42px; }
  .three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 30px; }
  .rule { border-top: 3px solid #087c83; padding-top: 20px; }
  .band { margin-top: 26px; padding: 18px 22px; background: #e5f2f1; font-size: 25px; }
  .flow { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 18px; }
  .step { border-top: 4px solid #087c83; background: #edf2f5; padding: 17px 20px; font-size: 22px; min-height: 112px; }
  .step b { display: block; font-size: 25px; margin-bottom: 8px; }
  .step span { font-size: 19px; color: #536975; }
  .proof { display: grid; grid-template-columns: 1fr 0.55fr 1.35fr; gap: 22px; align-items: start; margin-top: 32px; }
  .proof > div { border-top: 4px solid #087c83; padding-top: 20px; }
  code { background: #e9eff2; font-size: .82em; color: #142c3a; }
  pre { background: #edf2f5; font-size: 19px; padding: 20px; }
  table { font-size: 23px; width: 100%; }
  th { background: #e5f2f1; }
  .placeholder { border: 2px dashed #718d9a; height: 235px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 22px; box-sizing: border-box; background: #edf2f5; font-size: 23px; }
  .placeholder b { color: #087c83; font-size: 18px; letter-spacing: 1px; }
  .placeholder span { font-size: 19px; color: #536975; margin-top: 12px; }
---
<!-- _class: title -->
<!-- _footer: 'Andreas Krüger · Public repository: github.com/AndiKrue/fasttrack-termin · AGPL-3.0' -->

<div class="eyebrow" style="color:#6ed5cd">Open Agent Hackathon 2026</div>

# FastTrack Termin

<div class="lead">A faster route to a specialist appointment.<br><strong>With evidence for every reason.</strong></div>

Track 02: “The Agent That Can Explain Why”  
NVIDIA Nemotron prize submission

<div class="small" style="color:#c3d5dc;margin-top:30px">Berlin · Statutory-insurance patients · Prototype<br>Seed practices and waiting times are SAMPLE data. Not medical advice.</div>

<!-- Speaker notes: This deck covers rule 6.2: problem and users, solution, workflow and architecture, stack, sponsor use, uniqueness, product visual placeholders, and future work. No live availability or measured time saving is claimed. -->

---

<div class="eyebrow">Problem and target users</div>

# Waiting is only part of the problem

<div class="lead">Berlin statutory-insurance patients facing weeks of waiting may not know which route to try next.</div>

<div class="three" style="margin-top:32px">
<div class="rule"><h2>Appointment service</h2><p>What does the service offer, and which referral conditions apply?</p></div>
<div class="rule"><h2>Open consultation</h2><p>Could an appointment-free consultation be an option?</p></div>
<div class="rule"><h2>GP referral</h2><p>Could the GP help arrange the specialist appointment?</p></div>
</div>

<!-- Speaker notes: This is the target problem, not a measured waiting-time statistic. Route rules come from data/seed/rules.csv. The deck makes no independent legal interpretation and gives no clinical recommendation. -->

---

<div class="eyebrow">The solution</div>

# Ask once. Compare supported routes.

<div class="cols">
<div><h2>Patient input</h2><p>A question about location, specialty and referral situation.</p><p>The agent retrieves relevant rules, practice information and wait observations.</p></div>
<div><h2>Patient output</h2><p>Ranked routes with a reason and evidence IDs.</p><p>Each retained route exposes supporting rows with SQL or a web source URL.</p></div>
</div>

<div class="band">The goal: identify the fastest supported route in the available data.</div>

<p class="small">This prototype does not book appointments. SAMPLE waits are not live availability or a promise of access.</p>

<!-- Sources: ../../fasttrack/app.py and ../../fasttrack/agent.py (paths relative to this deck). The app shows routes, expected_days when present, reasons, evidence SQL and row, caveats, and the source/memory backend. -->

---

<div class="eyebrow">Agent workflow and architecture</div>

# The explanation has a data trail

<div class="flow">
<div class="step"><b>1 · Plan →</b>Find the factual questions.<br><span>Nemotron Lightning 30B</span></div>
<div class="step"><b>2 · SQL →</b>Query three Zetaris sources.<br><span>Rules · practices · waits</span></div>
<div class="step"><b>3 · Recall ↓</b>Retrieve earlier findings.<br><span>Meterless H-MEM</span></div>
<div class="step"><b>6 · Remember</b>Store only retained routes.<br><span>Run-linked memory</span></div>
<div class="step"><b>5 · Verify ←</b>Drop unsupported routes.<br><span>Nemotron Lightning 30B</span></div>
<div class="step"><b>4 · Answer ←</b>Rank routes; cite evidence IDs.<br><span>Nemotron Ultra 550B</span></div>
</div>

<p class="small">Between SQL and Recall: optional Firecrawl search + Lightning extraction. SQL/web rows share evidence IDs.</p>

<!-- Source: ../../fasttrack/agent.py, investigate(). Execution is sequential: plan, SQL queries, optional web search/extraction, recall, answer, verify, remember. SQL generation also uses Lightning. The snake layout follows that order. -->

---

<div class="eyebrow">What is unique</div>

# A reason points to an inspectable source

<div class="proof">
<div><h2>Claim</h2><p>A route and its factual explanation.</p><p class="small">No invented appointment promise.</p></div>
<div><h2>Evidence ID</h2><p><code>E1</code></p><p class="small">Illustrative ID</p></div>
<div><h2>Evidence object</h2><p><code>SQL + row</code> or <code>URL + row</code></p><p>Inspect the exact query result or a web fact and its source URL.</p></div>
</div>

<div class="band">The verifier is instructed to keep a route only when every factual statement is supported by its cited rows.</div>

<p class="small">Unknown IDs are removed; routes need a valid citation and a keep verdict. This is an LLM check, not a correctness guarantee.</p>

<!-- Source: ../../fasttrack/agent.py. Evidence IDs are assigned to SQL result rows and optional extracted web rows. Web evidence uses a search description in the sql field and a URL; it is not a SQL result. The verifier can remove whole routes; it does not rewrite individual claims. Draft caveats are passed through without the route-verification gate. No benchmark accuracy is claimed. -->

---

<div class="eyebrow">Zetaris</div>

# Three sources. One SQL surface.

| Source | What the agent retrieves |
| --- | --- |
| `FT_RULES.rules` | Route rules, applicability and legal references |
| `FT_PRACTICES.practices` | Practice directory and consultation attributes |
| `FT_WAITS.waits` | Channel-specific waiting-time observations |

<p><strong>Zetaris Lightning:</strong> Docker Compose platform; queries over JDBC.<br><code>zetaris/register.py</code> registers the seed CSV tables.</p>

<p class="small">Local fallback: SQLite with the same schemas. Seed practices/waits are SAMPLE. Optional Firecrawl adds real web practice facts with URLs; the answer prefers these rows.</p>

<!-- Sources: ../../fasttrack/sources.py and ../../zetaris/register.py. The configured backend is identified in the run trace. A local SQLite run does not demonstrate a live Zetaris integration. Rules are seed content, not newly validated legal advice. Optional Firecrawl search runs before recall. Lightning extracts stated page facts only; URLs are retained. doctolib, jameda, docinsider and sanego are excluded in fasttrack/web.py. No booking availability is inferred. -->

---

<div class="eyebrow">Meterless H-MEM</div>

# Memory keeps a link to its origin

<div class="cols">
<div><h2>Recall before answering</h2><p>A TypeScript bridge queries H-MEM for earlier findings relevant to the question.</p><p>Recalled findings provide context; the answer still needs current evidence rows.</p></div>
<div><h2>Remember after verification</h2><p>Retained route and reason become factual memory with a run tag and <code>fasttrack:&lt;run_id&gt;</code> source.</p><p>H-MEM persists state and a ledger.</p></div>
</div>

<p class="small">Current provenance boundary: H-MEM stores text and the run link. Full SQL/rows are in the returned evidence; the JSONL fallback stores the full record.</p>

<!-- Sources: ../../fasttrack/memory.py and ../../meterless/bridge.ts. investigate passes the complete evidence record to remember; the H-MEM bridge currently selects content, tags and source, rather than storing full row/SQL payloads. Do not imply complete row provenance is embedded in H-MEM. Vendored H-MEM is Apache-2.0; repository code is AGPL-3.0. -->

---

<div class="eyebrow">Technical stack and NVIDIA Nemotron</div>

# Four roles, with separate model choices

| Role | Configured model | Responsibility |
| --- | --- | --- |
| Planner | Lightning 30B | Select factual questions |
| SQL | Lightning 30B | SELECTs and web search query |
| Verifier | Lightning 30B | Route checks; web fact extraction |
| Answer | Ultra 550B | Rank routes and explain why |

<p><strong>Python:</strong> agent, HTTP app, <code>httpx</code>, JDBC via <code>jaydebeapi</code>.<br><strong>Node / TypeScript:</strong> <code>tsx</code> bridge to Meterless H-MEM.<br><strong>Browser:</strong> HTML/CSS/JavaScript question and evidence view.</p>

<p class="small">NVIDIA API · Optional Firecrawl: cloud or self-hosted · No measured gains claimed.</p>

<!-- Source: ../../fasttrack/llm.py. Defaults: nvidia/nemotron-3.5-lightning-30b-a3b for planner/sql/verifier; nvidia/nemotron-3-ultra-550b-a55b for answer. FT_MODEL_* overrides are supported. Configuration is not evidence of a successful live run. The model-call trace records model, role, time and token usage when returned. -->

---

<div class="eyebrow">Product visuals</div>

# Show the route, then inspect the reason

<div class="cols">
<div><h2>Ask and compare</h2><div class="placeholder"><b>SCREENSHOT PLACEHOLDER A</b><p>Question + ranked route cards</p><span>Insert an actual app capture.<br>Keep the SAMPLE label visible.</span></div></div>
<div><h2>Inspect the evidence</h2><div class="placeholder"><b>SCREENSHOT PLACEHOLDER B</b><p>Evidence ID + SQL / URL + row</p><span>Insert an actual app capture.<br>Include source / memory backend.</span></div></div>
</div>

<p class="small">Placeholders only. No screenshots or live-run results are represented on this slide.</p>

<!-- Capture guidance: use fasttrack/app.py at localhost. Show the question, a retained route, its why text, evidence IDs with SQL/rows, and backend labels. Hide any personal information. Replace placeholders only with actual product captures; do not fabricate outputs. -->

---

<div class="eyebrow">Future work</div>

# From sample routes to real access

<div class="three">
<div class="rule"><h2>Real practice data</h2><p>Expand web coverage; replace SAMPLE waits with maintained data.</p><p class="small">Track freshness and source provenance.</p></div>
<div class="rule"><h2>Booking integration</h2><p>Connect supported routes to booking services.</p><p class="small">Confirm availability and obtain patient approval before booking.</p></div>
<div class="rule"><h2>Other cities</h2><p>Extend directories and validate local route information.</p><p class="small">Keep the same evidence and verifier contract.</p></div>
</div>

<div class="band">Next validation: live integrations, verifier failure cases, and complete row provenance in H-MEM.</div>

<p class="small">Public source: <a href="https://github.com/AndiKrue/fasttrack-termin">github.com/AndiKrue/fasttrack-termin</a></p>

<!-- Future work is proposed, not implemented. Source baseline inspected: 0d8afd12198829c0404480f980310bc564daec77. Re-export with Marp CLI and Chromium: npx @marp-team/marp-cli@4.5.1 docs/deck/deck.md --html --pdf -o docs/deck/deck.pdf. No keys or personal patient data belong in the deck. -->
