<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# FastTrack Termin — code review

Ranked improvement plan for the Python agent, Zetaris sources, H-MEM bridge, Nightshift/Nemotron, Firecrawl, web UI and Telegram mini app. Source: repository at review time (28 Oct 2026).

| 12 | 5 | Filter | 7 / 10 / 12 |
|---|---|---|---|
| Findings (P0–P2) | P0 patient / reliability | Verifier, not a loop | Rules / practices / waits rows |

**Main failure mode for patients.** A typical question (“I live in Köpenick… orthopaedics”) can generate `district = 'Köpenick'` against seed borough `Treptow-Köpenick`, skip `FT_RULES`, then drop every slightly over-claimed route. The UI then says no route survived verification — even though R4 (open consultation) and P01/W01 (0 days) are in the data.

## Ranked findings

| # | Sev | Area | Where | What / why it matters |
|---|---|---|---|---|
| 1 | P0 | SQL vs seed | fasttrack/agent.py:26–37 · data/seed/practices.csv:2–11 | Filters use locality names (Köpenick) and German specialties (HNO); seed uses boroughs (Treptow-Köpenick) and English (ENT). Empty joins → no route. |
| 2 | P0 | Rules unused | fasttrack/agent.py:20–25, 62–63 | Planner is not required to query FT_RULES. Patients miss 116117 / four-week / open-consultation rights. |
| 3 | P0 | Verifier is a filter | fasttrack/agent.py:47–51, 115–135 | Unsupported routes are dropped. No rewrite. One over-claim can leave the patient with zero routes. |
| 4 | P0 | No outage path | fasttrack/sources.py:96–98 · llm.py:47–57 · app.py:120–122 | Zetaris jar set with a dead JDBC, or Nightshift/NVIDIA down, fails the whole /ask. No sample LLM without keys. |
| 5 | P0 | Public PHI surface | compose.yaml:24–27 · app.py:92–108 · memory.py:29–31 · bridge.ts:13–15 | Cloudflare tunnel exposes unauthenticated /ask. Questions (health data) go to NVIDIA, Firecrawl, H-MEM disk, and client traces. |
| 6 | P1 | H-MEM recall weak | meterless/hmem/src/embeddings.ts:9–14 · bridge.ts:13–25 | Tokeniser strips umlauts; embeddings are 64-d hashes; bridge stores text not evidence rows. Similar German questions often miss. |
| 7 | P1 | JDBC leak + no timeout | fasttrack/sources.py:61–83 · agent.py:55 | Every investigate() opens a new Lightning connection and never closes it. No query timeout or reconnect. |
| 8 | P1 | Empty SQL not retried | fasttrack/agent.py:74–86 | A 0-row SELECT is stored as success with no evidence. Model is not asked to relax district/specialty. |
| 9 | P1 | Seed has no phone/address | data/seed/practices.csv:1–11 · static/app.js:189–194 | Call/route buttons only appear on Firecrawl rows. SAMPLE cards are explanation-only. |
| 10 | P1 | English-only UX | static/index.html:3 · app.js:441–444 · miniapp.html:3, 256–275 | lang=en, answers read in en-US, mini app shows raw SQL/JSON not plain-language facts. |
| 11 | P1 | SQL guard is a regex | fasttrack/sources.py:27–36 | Blocks DML keywords and `;`. Allows UNION, comments, and any table name. Prompt injection can still dump or confuse. |
| 12 | P2 | Shared HTTP client in threads | fasttrack/agent.py:69–71 · llm.py:59, 75 | SQL drafts and Firecrawl extraction share one httpx.Client; list appends race. 429/5xx are not retried. |

Line numbers refer to the reviewed tree. P0 = empty or unsafe answer for a patient, or total outage.

## 1. Zetaris sources vs generated SQL

### Value catalogue mismatch (empty queries)

SQL prompt lists “Mitte or Treptow-Köpenick” and English specialties, but does not list the seven seed specialties or the twelve Berlin boroughs. Examples in the UI say Köpenick, Friedrichshain, Pankow, Charlottenburg.

| User / model says | Seed value | Rows if equality |
|---|---|---|
| Köpenick | Treptow-Köpenick | 0 (P01, P04, P08 missed) |
| Friedrichshain | Friedrichshain-Kreuzberg | 0 (P03 missed) |
| Charlottenburg | Charlottenburg-Wilmersdorf | 0 (P05 missed) |
| HNO / Hals-Nasen-Ohren | ENT | 0 (P08 missed) |
| Orthopädie | orthopaedics | 0 unless lower() + English |
| topic = 'offene Sprechstunde' | open consultation | 0 (R4 missed) |

### FT_RULES is optional (rules)

PLANNER asks for “up to 5 short questions, each answerable by one SQL query” and never requires one per source. The SQL role is not told “legal / 116117 / referral / open consultation → FT_RULES.rules”. Tests pass because FakeLLM hard-codes a rules SELECT.

### What returns empty

Equality on the wrong district or specialty; German topic/channel strings; Lightning uppercase column names without aliases; a bad JOIN (waits.practice_id to practices); or a thrown SQL that is recorded as `error` and skipped. 0-row success is indistinguishable from “no such practices exist”.

**Concrete SQL fix.** Put the exact allowed values in SCHEMA (districts, specialties, yes/no, channels, rule topics). In Python, map locality nicknames to boroughs before execute. If row count is 0, rewrite once with `LIKE` / `IN (borough, locality)`. Inject a rules question when the plan omitted FT_RULES.

## 2. Agent architecture

Flow is plan → SQL+web → recall → answer → verify-and-drop → remember. The verifier returns `keep: [indexes]`. Kept routes must also have a remaining evidence id. There is no second answer call. Caveats are never checked.

### Smallest revision loop

After verify, if `kept` is empty or any route was dropped, call the answer role once more with: the original evidence rows, the dropped routes, and the verifier notes. Instruct it to rewrite or replace claims, still citing only existing ids. Run verify once. Stop. That is one extra Lightning call in the failure case, not an unbounded loop.

Do not ask the verifier to invent new SQL. If evidence itself is empty, the retry belongs in the query step (finding 8), not here.

## 3. Memory

### Local JSONL

Token overlap on words longer than 3 characters over the full record, including evidence. “knee Köpenick” recalls. Short tokens (GP, ENT) are ignored.

### H-MEM bridge

Each remember/recall spawns `tsx bridge.ts`, loads `runs/hmem/state.json`, stores `question -> route: why` at confidence 0.8, queries at threshold 0.2 (default H-MEM is 0.35). Evidence rows are discarded. The vendored embedder hashes ASCII tokens only: `Köpenick` becomes `k` + `penick`.

**Does recall return earlier findings?** Sometimes, when the new question shares long ASCII tokens with the old one (orthopaedics, dermatology). Not reliably for German paraphrases, umlauts, or “same specialty, other district”. There is no automated test of the bridge. A remember() exception after a good answer fails the HTTP request.

## 4. Robustness

| Dependency | Timeout | Retry | Fallback today |
|---|---|---|---|
| Zetaris JDBC | none | none | LocalSource only if ZETARIS_JDBC_JAR unset; never on connect fail |
| Nightshift / Nemotron | 120 s httpx | JSON parse ×2 then fallback model | No HTTP 429/5xx retry; Nightshift down does not fall back to NVIDIA |
| Firecrawl | 60 s + 20 s extract | none | Optional: missing key or exception → continue without web |
| H-MEM | 60 s subprocess | none | LocalStore only if tsx missing at open; recall/remember errors propagate |
| Telegram API | 40 s | 5× backoff, 429 retry_after | Poll loop never exits |

Sample mode without credentials does not exist: `Nemotron()` in `app.main` requires a Nightshift runtime token or `NVIDIA_API_KEY`. LocalSource already covers data. Missing piece is a canned or recorded LLM for planner/sql/answer/verifier.

## 5. Security and privacy

unauthenticated /ask · SQL regex guard · PHI in traces · Telegram token redacted · Maps key not in access log

`check_sql` is a real read-only fence for semicolon-stacked DML, not a table whitelist. Secrets live in gitignored `.env` (good). The Maps embed key is returned on `/config` by design and tested as absent from the request log. Exception text (first 400 chars) is sent to the browser. Patient questions are stored in JSONL/H-MEM and echoed in NDJSON traces. Nominatim is called from the browser with practice addresses.

## 6. UX and accessibility

### What works

Acute 112 / 116117 panel is hard-coded, not model-chosen. Streaming timeline, evidence chips, reduced-motion on scroll, focus-visible, aria-live on results, tel: links, OSM fallback when Maps is off, HTML-escaped Telegram messages.

### German users

Pages are `lang="en"`. Copy, examples, caveats, and TTS are English. Mic follows browser language; read-aloud is forced en-US. Web Speech inside Telegram WebView is unreliable — a later STT/TTS path is the right fix.

### Evidence language

Web UI “Why this route” still dumps column keys. Mini app shows SQL + JSON in `<details>`, not a fact sentence. Empty verify state tells the user to open the trace instead of naming the missing district/rules query.

## 7. Tests that are missing

| Covered today | Should add |
|---|---|
| Citation strip, dropped-route notes, SQL keyword guard, 7 rules rows | Equality on Köpenick vs Treptow-Köpenick returns 0; synonym map then hits P01 |
| FakeLLM always queries rules | Planner/agent injects FT_RULES when the model omits it |
| JSON parse + Nightshift headers + Ultra fallback | HTTP 429/5xx retry; Nightshift → NVIDIA failover |
| Firecrawl URL binding, 3×3000 chars, slow page drop | H-MEM bridge round-trip; umlaut query still recalls |
| Telegram HTML escape, token redact, split messages | investigate() with empty evidence → one answer retry |
| /config maps key not logged | Sample LLM path; JDBC connect fail → local; table whitelist in check_sql |

## Five work orders first

Each is one change set: prompt + a few Python lines + tests. No new services.

- **WO1 SQL catalogue:** list exact seed districts, specialties, channels, topics in SCHEMA; map Köpenick→Treptow-Köpenick (and the other nicknames) in sources.query; one LIKE retry on 0 rows. Test the empty-then-hit path.
- **WO2 Force rules:** if the plan has no question that will hit FT_RULES, append one. Tell the SQL role which table answers which kind of question. Test with a FakeLLM that only asks for practices.
- **WO3 One revision:** when kept is empty after verify, call answer once with dropped notes + rows, then verify once. Cap at one retry. Test Strict FakeLLM that fails the first keep set.
- **WO4 Degraded run:** FT_SAMPLE=1 (or missing keys) uses LocalSource + recorded JSON replies; if JDBC connect fails, log and use local-sqlite without calling it Zetaris; Nightshift HTTP errors fall back to NVIDIA_API_KEY when set.
- **WO5 Memory that actually recalls:** normalise umlauts in bridge.ts before embed/query; on bridge error use LocalStore; wrap remember so a failed write cannot 500 a good answer; add tests/test_hmem_bridge.py.

After these five: whitelist tables in check_sql, reuse one JDBC connection with a timeout, German UI strings, and plain-language evidence sentences in the mini app.

## Five changes first

The ranked plan is in the canvas FastTrack review — a canvas beside the chat so you can scan severity, SQL mismatches, and the five work orders without scrolling a long table. Below is the same review with file and line citations.

**Headline:** A typical Köpenick orthopaedics question can return **no routes** even though R4, P01 and W01 are in the seed. The SQL layer misses borough names, `FT_RULES` is optional, and the verifier only deletes claims — it never rewrites them.

---

### 1. Zetaris sources vs generated SQL — **highest impact**

**District and specialty values do not match the seed.**
`fasttrack/agent.py` 26–37 tells the model “district is a Berlin borough such as Mitte or Treptow-Köpenick” and “specialty is lower-case English (dermatology, orthopaedics, … ENT)”. The UI examples say *Köpenick*, *Friedrichshain*, *Pankow*. Seed districts are the official boroughs:

```
P01,Sample Practice Orthopaedics Köpenick,Treptow-Köpenick,orthopaedics,5,yes,yes,SAMPLE
P02,Sample Practice Orthopaedics Mitte,Mitte,orthopaedics,5,no,yes,SAMPLE
P03,Sample Practice Dermatology Friedrichshain,Friedrichshain-Kreuzberg,dermatology,5,yes,no,SAMPLE
```

`district = 'Köpenick'` or `specialty = 'HNO'` / `'Orthopädie'` returns **zero rows**. The query is logged as success with an empty evidence list (`agent.py` 74–86). The patient is told there is no backed route, not that the filter was wrong.

**`FT_RULES` is not actually required.**
Planner (`agent.py` 20–25, 62–63) asks for “up to 5 short questions”, not one per source. The SQL prompt never says “116117 / referral / open consultation / legal basis → `FT_RULES.rules`”. Rule topics in `data/seed/rules.csv` are English (`open consultation`, `appointment service`). A German `topic` filter misses R4 — the five open-consultation hours that justify the fastest route. Tests pass because `FakeLLM` always issues a rules SELECT (`tests/test_agent.py` 18–21).

**Joins and channels are otherwise aligned** if the filters are right: `practice_id`, `channel` values `open consultation` / `phone` / `online` / `appointment service`, `yes`/`no` strings, `days_to_appointment` as integers. Lightning `inferSchema` (`zetaris/register.py` 52) can still uppercase column names; the mini app lowercases keys, the main UI does not (`app.js` 189–194).

**What makes queries empty:** wrong district/specialty/topic equality; German vs English; a thrown SELECT recorded as `error` and skipped; 0-row success with no retry. There is no “relax the filter” step.

**Fix:** Put the exact seed enumerations in `SCHEMA`. Map nicknames in Python (`Köpenick` → `Treptow-Köpenick`, `Friedrichshain` → `Friedrichshain-Kreuzberg`, `HNO` → `ENT`). On 0 rows, retry once with `LIKE` or `IN (borough, locality)`. If the plan never mentions rules, append one question that SELECTs from `FT_RULES.rules`.

---

### 2. Agent architecture — filter, not a loop

```
VERIFY = (
    "Check each route against the cited evidence rows. Keep a route only if every factual "
    "statement in it is supported by its cited rows. "
    'Return {"keep": [indexes of supported routes], "notes": ["why a route was dropped"]}.'
)
```

After answer, unknown evidence ids are stripped, then `keep` indexes retain a subset (`agent.py` 112–135). Dropped routes are shown; nothing is sent back to the answer role. Caveats are never verified. If the verifier is strict or uses 1-based indexes, **kept can be empty**.

**Smallest revision loop:** If `kept` is empty (or any route was dropped), call answer **once** with the same evidence rows plus dropped text and verifier notes; instruct it to rewrite using only existing ids; verify **once**; stop. If evidence itself is empty, retry belongs in SQL (finding 1), not here.

---

### 3. Memory — recall is fragile

`LocalStore.recall` (`memory.py` 33–44) scores words longer than 3 characters over the full JSON, including evidence. That can work for “knee Köpenick”.

`HMemStore` (`memory.py` 56–74, `meterless/bridge.ts` 11–36) starts a new Node process per call, stores `question -> route: why` at confidence 0.8, queries at threshold 0.2. **Evidence rows are dropped.** The vendored tokeniser strips non-ASCII:

```
export function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 1);
}
```

`Köpenick` becomes `k` + `penick`. Embeddings are 64-d FNV hashes, not semantic. Similar German questions often miss. `remember()` after a good answer is not wrapped; a bridge failure 500s the request (`agent.py` 137–138). `open_memory()` falls back to JSONL only if `tsx` is missing, not if recall throws.

---

### 4. Robustness

| Layer | What exists | Gap |
|---|---|---|
| Zetaris | `LocalSource` if `ZETARIS_JDBC_JAR` unset (`sources.py` 96–98) | Jar set + dead JDBC → hard fail. **New connection per `investigate()`, never closed** (`sources.py` 66–83, `agent.py` 55). No timeout. |
| Nemotron | 120s timeout; JSON retried twice then `FT_MODEL_FALLBACK` (`llm.py` 47–113) | No 429/5xx retry. Nightshift configured ⇒ NVIDIA is not a failover. |
| Firecrawl | Optional; exceptions recorded (`agent.py` 96–97, `web.py` 66–80) | Search itself has no retry. |
| Demo | SQLite seed works | **`Nemotron()` requires keys** (`app.py` 120–122). No sample LLM. |

Telegram polling does retry (`telegram_bot.py` 50–66). Firecrawl extract has a 20s cap. SQL drafts share one `httpx.Client` from a thread pool (`agent.py` 69–71) — not a documented thread-safe pattern; `calls` appends can race.

---

### 5. Security and privacy

- **SQL guard** (`sources.py` 27–36): one SELECT, no `;`, no DML keywords. Allows `UNION`, comments, and **any table**. The threat is the model (and prompt injection through the patient question), not a human SQL console.
- **Unauthenticated `/ask` and `/ask/stream`** (`app.py` 92–108) plus Cloudflare tunnel (`compose.yaml` 24–27) = public inference and **PHI in the body**.
- Questions persist in `runs/memory.jsonl` and `runs/hmem/` (`memory.py` 29–31, `bridge.ts` 13–15) and in NDJSON traces.
- Exception text (400 chars) is sent to the client (`app.py` 108).
- Telegram token is redacted (`telegram_bot.py` 47–48, 70–78 in tests). Maps embed key is on `/config` by design and is tested not to appear in the access log (`tests/test_app.py` 36–40). `.env` loading does not print values (`env.py` 4–6).
- Browser Nominatim lookups leak addresses to OSM (`app.js` 361–375).

**Fix (small):** Shared secret or Telegram `initData` check on POST; whitelist `FT_RULES.rules|FT_PRACTICES.practices|FT_WAITS.waits`; do not persist raw questions without a retention note; wrap `remember` so memory failure cannot fail the answer.

---

### 6. UX and accessibility

**Solid:** Hard-coded 112/116117 panel (`app.js` 51–67), streaming steps, `aria-live`, focus-visible, reduced-motion on scroll, `tel:` links, OSM if Maps is off, Telegram HTML escape.

**Weak for German users:** `lang="en"` (`index.html` 3, `miniapp.html` 3). All product copy and examples are English. Mic follows `navigator.language`; **read-aloud is forced `en-US`** (`app.js` 441–444). Web Speech inside Telegram WebView is unreliable.

**Evidence is not plain language:** Web “Why this route” dumps `key: value` (`app.js` 205–211). Mini app shows SQL + JSON in `<details>` (`miniapp.html` 269–275). Empty verify copy tells people to open the trace (`app.js` 299–300) instead of “the district filter matched no practices; rules were not queried.”

Seed practices have **no phone or address**, so Call/Route only appear on Firecrawl rows (`practices.csv` vs `app.js` 189–194). SAMPLE cards cannot be acted on.

---

### 7. Tests that should exist

Covered: citation stripping, dropped-route notes, keyword SQL guard, rule row count 7, JSON parse, Nightshift headers, Firecrawl URL binding, Telegram escape/token, maps key logging.

**Missing:** Köpenick vs `Treptow-Köpenick` (0 then mapped hit); agent injects `FT_RULES` when FakeLLM omits it; one answer retry when verify keeps nothing; H-MEM bridge round-trip and umlaut query; JDBC fail → local; `FT_SAMPLE` path; table whitelist; Nightshift HTTP failover to NVIDIA.

---

### Five work orders first

Each is one change set (prompt + a little Python + tests).

1. **SQL catalogue + nickname map** in `SCHEMA` / `sources.query`, one `LIKE` retry on 0 rows. Test empty-then-P01.
2. **Force a rules question** if the plan has none; tell the SQL role which table answers which question. Test a practices-only FakeLLM.
3. **One revision:** empty `kept` → answer once with verifier notes → verify once.
4. **Degraded run:** `FT_SAMPLE=1` or missing keys → `LocalSource` + canned JSON; JDBC connect fail → `local-sqlite` (never labelled Zetaris); Nightshift HTTP errors → `NVIDIA_API_KEY` if set.
5. **Memory that recalls:** umlaut-normalise in `bridge.ts` (leave vendored H-MEM alone); LocalStore on bridge error; `remember` must not 500 a good answer; `tests/test_hmem_bridge.py`.

After that: table whitelist, one reused JDBC connection with a timeout, German strings, and fact sentences in the mini app instead of raw JSON.
