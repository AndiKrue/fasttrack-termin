<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# WO-FT-ASK-01: who may ask, and how long questions are kept (DRAFT, owner's decision)

| Field | Value |
|---|---|
| Source | Grok review finding 5 (P0), listed under "Not in this WO" in `WO-FT-REVIEW-01.md` |
| Branch | `review` (draft commit, **off by default**) |
| Deploy | Only after the owner picks an option below, and not before 6 Nov 2026 16:00 UTC |
| Readiness | DRAFT. The code is in place but does nothing until `FT_ASK_AUTH=on`. |

## Problem

`POST /ask` and `POST /ask/stream` answer anyone who knows the quick-tunnel URL. A patient's question
is health data (specialty, district, complaint). Each request also spends model calls (NVIDIA / Nightshift)
and a Firecrawl search.

The Telegram chat bot is not affected: it calls the agent in-process, not over HTTP.

## What the draft does (`fasttrack/auth.py`)

- `FT_ASK_AUTH` unset or anything other than `on`: no check. This is today's behaviour.
- `FT_ASK_AUTH=on`: a question passes when one of these holds:
  1. **Telegram mini app.** The header `X-Telegram-Init-Data` carries `Telegram.WebApp.initData`.
     - It must be signed by `TELEGRAM_BOT_TOKEN` or `TELEGRAM_BOT_TOKEN_TEST`.
     - The check is Telegram's HMAC-SHA256 with the key `HMAC("WebAppData", bot token)`.
     - `auth_date` must be at most 24 hours old.
     - The mini app already sends this header. While the check is off, the server ignores it.
  2. **Shared key.** The header `X-FT-Key` equals `FT_ASK_SECRET`.
     - The web page (`/`) asks for the key once after a 401 and keeps it in sessionStorage for that tab only.
     - The key never goes in the URL, so it never appears in the request log.
- A refused request gets a 401 with a short JSON error, before any model call.

Tests: `tests/test_auth.py` covers:

- a valid signature, a foreign bot, a tampered payload, stale data and an empty key;
- the 401 on both endpoints, with the agent never running.

## Decisions for the owner

1. **Which option?**
   - **A: on, mini app plus key.** Recommended: the judged web page keeps working for you with the key, and strangers get a 401.
   - **B: on, mini app only.** Leave `FT_ASK_SECRET` empty. The public web page then always shows 401; use the host's `127.0.0.1:8765` page through an SSH tunnel or locally. **Note:** port-published requests do not arrive as loopback inside the container, so the draft has no loopback exception.
   - **C: off.** Keep it off until the judging period ends, and decide afterwards.
2. **Accept the test bot's signature on the live app?** The draft accepts both tokens. To accept only the live bot there, drop `TELEGRAM_BOT_TOKEN_TEST` from the live `.env`, or narrow `BOT_TOKENS`.
3. **Retention.** Where a question ends up today:
   - **H-MEM** (`runs/hmem/state.json`, `ledger.jsonl`): the question, the route and the reason of every verified route. Kept indefinitely; there is no deletion.
   - **Sample mode** (`runs/sample-memory.jsonl`): the same fields, kept indefinitely.
   - **Model providers**: NVIDIA API and, if configured, Meterless Nightshift (check whether its receipts and local logs store prompt text). Firecrawl receives a derived German search query.
   - **App logs**: the request line and status only. The question text is not logged.

   Proposal:
   - delete memory records older than 30 days at start-up;
   - add one line to the page and the mini app: "Questions are stored with the verified answer for 30 days to improve later answers.";
   - add `FT_MEMORY=local` with an empty file as the opt-out.

   Not in this draft; needs your yes.

## Deploy (after the decision, not before 6 Nov 16:00 UTC)

Option A in the live `.env`:

```
FT_ASK_AUTH=on
FT_ASK_SECRET=<long random string, never committed>
```

Then rebuild the app from `post-hackathon` once `review` is merged there. Check:

- the mini app answers;
- `curl -X POST <tunnel>/ask` returns 401;
- the web page asks for the key and then answers.
