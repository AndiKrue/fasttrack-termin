<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# WO-FT-REVIEW-01 — the five changes from the Grok code review

| Field | Value |
|---|---|
| Repo | `fasttrack-termin` (`C:\Tools\fasttrack-termin`) |
| Source | `docs/review/GROK-REVIEW-2026-10-28.md`, section "Five changes first" (Grok, xAI, in Cursor, recorded 28 Oct 2026; reviewed tree `post-hackathon` `706f155`) |
| Branch | `review` from `post-hackathon`. **Nothing goes to `main`.** |
| Start | **After the results call, 6 Nov 2026 16:00 UTC.** This document is a draft; no code changes before then. |
| Deploy | Through `post-hackathon` after each part passes its tests and one live run on the test port (8766). |
| Executor | Claude Code on the laptop |
| Readiness | DRAFT |

## 0. What this covers

Grok ranked twelve findings and proposed five work orders. Each of the five below is one part of this WO with its
own commit(s). Before writing this WO, Claude Code checked each finding against the code at `706f155`. Where the
review is off, the part says so.

Deduplicated against "Known issues" in `docs/HANDOFF-2.md`:

| Known issue (HANDOFF-2) | Here |
|---|---|
| 1. `district = 'Köpenick'` vs `Treptow-Köpenick` → empty results | Part 1 |
| 2. Rules table rarely queried | Part 2 |
| 3. `enable_thinking=false` may not reach the model through Nightshift | **Not in the review.** Stays a separate item (check Nightshift receipts, ask in Help Meterless). |
| 4. No automated test for the H-MEM bridge | Part 5 |
| 5. No sample mode without credentials | Part 4 |
| 6. Verifier filters but never sends routes back for revision | Part 3 |

## 1. SQL catalogue and nickname map (Grok finding 1, P0; WO1)

**Problem.** The SQL prompt (`fasttrack/agent.py` `SQL`) names only examples ("Mitte or Treptow-Köpenick",
"dermatology, orthopaedics, cardiology, ENT, ..."). The seed uses official borough names and English specialties:

- districts: Charlottenburg-Wilmersdorf, Friedrichshain-Kreuzberg, Lichtenberg, Mitte, Neukölln, Pankow,
  Steglitz-Zehlendorf, Treptow-Köpenick
- specialties: cardiology, dermatology, ENT, gynaecology, neurology, ophthalmology, orthopaedics
- rule topics: appointment service, open consultation, GP referral, acute care, psychotherapy
- channels: open consultation, phone, online, appointment service

A question about "Köpenick", "Friedrichshain" or "HNO" yields an equality filter that returns 0 rows. The
query is recorded as a success with an empty evidence list (`agent.py` query loop), so the answer has nothing
to cite.

**Change.**
1. Put the exact allowed values in the SQL prompt. Generate them from the seed at import (`data/seed/*.csv`)
   rather than hard-coding them, so the prompt follows the data.
2. A small nickname map in Python, applied to the SQL before execution: Köpenick → Treptow-Köpenick,
   Friedrichshain/Kreuzberg → Friedrichshain-Kreuzberg, Charlottenburg/Wilmersdorf → Charlottenburg-Wilmersdorf,
   Steglitz/Zehlendorf → Steglitz-Zehlendorf, HNO → ENT, Orthopädie → orthopaedics, Hautarzt/Dermatologie →
   dermatology, Kardiologie → cardiology, Augenheilkunde → ophthalmology, Gynäkologie/Frauenarzt →
   gynaecology, Neurologie → neurology.
3. When a SELECT returns 0 rows, redraft it once and tell the SQL role "0 rows; relax the district/specialty
   filter (LIKE or IN)". Record both attempts in the trace.

**Tests.** `LocalSource`: `district = 'Köpenick'` returns 0; after the map, P01 is returned. Agent with a fake
LLM that first writes the 0-row query: one redraft, then P01 evidence appears.

## 2. Always consult the rules (Grok finding 2, P0; WO2)

**Problem.** The planner asks for "up to 5 short questions" and never requires one for `FT_RULES.rules`. The
SQL prompt never says which table answers which kind of question. The tests miss this because `FakeLLM` always
returns a rules SELECT (`tests/test_agent.py`).

**Change.**
1. In the SQL prompt: rules, rights, 116117, referral, urgency code, open consultation → `FT_RULES.rules`;
   practices, district, specialty → `FT_PRACTICES.practices`; waiting days, channel → `FT_WAITS.waits` joined
   on `practice_id`.
2. After planning, if no question mentions rules, append one fixed question that selects the relevant rules
   (`SELECT rule_id, topic, rule, legal_basis FROM FT_RULES.rules`). There are only 7 rows, so selecting all of
   them is cheap.

**Tests.** A fake LLM whose planner asks only about practices: the agent still runs a rules query, and the
evidence contains rule rows.

## 3. One revision after the verifier (Grok finding 3, P0; WO3)

**Problem.** The verifier returns `keep: [indexes]`. Unsupported routes are dropped and never sent back. One
over-claim can leave the patient with no routes, even though supported evidence exists.

**Change.** When `kept` is empty, call the answer role once more with the same evidence rows, the dropped routes
and the verifier notes. It must rewrite or replace those claims and cite only existing ids. Then verify once and
stop. Mark the revision as its own step in the trace ("revise"). Only one extra round, and only when nothing
survived. Do not run it when some routes were kept. Do not let the verifier write SQL.

**Tests.** A strict fake verifier that keeps nothing on the first pass and keeps index 0 on the second: one
answer retry, one route kept, the trace shows the revise step. A fake LLM whose first verify keeps a route: no
retry.

## 4. Degraded run and sample mode (Grok finding 4, P0; WO4)

**Problem.** Without a Nightshift token or `NVIDIA_API_KEY`, `Nemotron()` raises at start (`app.main`). If
`ZETARIS_JDBC_JAR` is set but Lightning is down, `ZetarisSource()` raises on every request. Nightshift being down
does not fall back to the NVIDIA API.

**Change.**
1. `FT_SAMPLE=1` (or no model credentials at all): `LocalSource` plus recorded model replies for
   planner/sql/answer/verifier, stored as JSON under `tests/fixtures/` or `data/sample/`. The UI footer says
   "sample mode". Every answer stays labelled SAMPLE.
2. JDBC connect failure: log it and use `local-sqlite`. The footer then shows `local-sqlite`, never "Zetaris".
3. Nightshift HTTP errors (connection refused, 5xx) fall back to the NVIDIA API when `NVIDIA_API_KEY` is set.
   Record the provider per call, as now.

**Tests.** `FT_SAMPLE=1` with no keys returns at least one route. A failing JDBC connect yields `source ==
"local-sqlite"`. A Nightshift 503 with a key set yields one call on `nvidia-api`.

## 5. Memory that recalls, and cannot fail an answer (Grok findings 6 and 7, P1; WO5)

**Problem.**
- The vendored H-MEM tokenizer (`meterless/hmem/src/embeddings.ts`) keeps only `[a-z0-9]`, so "Köpenick"
  becomes "penick" (the lone "k" is filtered out). The review says "k + penick".
- The embedder is a 64-dimension hash, so German paraphrases and umlauts often miss.
- `memory.remember()` runs unguarded after a verified answer (`agent.py` remember loop). A bridge failure turns
  a good answer into an HTTP error.
- `open_memory()` falls back to JSONL only when the bridge is missing at start, not when a call fails.
- No test exercises the bridge.

**Change.**
1. Normalise text in `meterless/bridge.ts` before `add` and `query`: ä→ae, ö→oe, ü→ue, ß→ss, then lower-case.
   **Do not edit the vendored `meterless/hmem/src`.**
2. Wrap `remember` and `recall` in the agent. A memory failure becomes a trace entry
   (`{"step": "recall", "error": ...}`) and never fails the request.
3. `tests/test_hmem_bridge.py`: remember a Köpenick route, then recall it with "Knie Koepenick Orthopäde". The
   test skips when `tsx` is not installed.

## 6. Not in this WO (from the same review, for later work orders)

- **Unauthenticated `/ask` behind the public tunnel (Grok finding 5, P0).** Patient questions are health data.
  Check Telegram `initData` or a shared secret on POST, and add a retention note for stored questions. Grok
  ranked this P0 but left it out of its five. It needs a decision by the owner and should be the next WO.
- **SQL guard** (finding 11): whitelist the three tables in `check_sql`.
- **JDBC connection reuse** (finding 7): one connection with a timeout instead of one per `investigate()`.
- **Shared httpx client across threads** (finding 12): 429/5xx retry.
- **Seed rows without phone or address** (finding 9).
- **German UI and plain-language evidence** (finding 10): branch `miniapp-ux` covers the mini app evidence.
  The read-aloud language follows WO-FT-VOICE-01.

## 7. Rules

- Commit as `Andreas Krüger <AndiKrue@users.noreply.github.com>`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Stage files by name. Never commit `.env`, audio, video or `bot-qr.png`.
- No new dependencies. Keep every existing behaviour, including the judged stack and the browser fallbacks.
- Tests: `python -m pytest -q` green in a clean environment (no `.env` loaded), plus one live question on
  port 8766 per part.
- Closeout: `docs/wo/CLOSEOUT-WO-FT-REVIEW-01.md` listing what was verified live and what was not.
