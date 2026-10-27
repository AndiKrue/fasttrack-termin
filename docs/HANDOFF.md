# Handoff: FastTrack Termin, Open Agent Hackathon 2026

For the Claude session that runs directly on the owner's laptop (`C:\Tools\fasttrack-termin`) and takes over
development from the cloud session. Read this file fully before the first change.

## Deadline

- Submission closes **27 Oct 2026, 23:59 UTC**. Code freeze **23:15 UTC**; after that only docs, video and submission.
- Deliverables: video (1–4 min), deck (`docs/deck/deck.pdf`), public repo with README, sponsor-tech explanation.
- Rule 5.1: the entry must integrate **Zetaris** and **Meterless**. Target track: 02 "The Agent That Can Explain Why",
  plus the "Best use of NVIDIA Nemotron" prize.

## What it is

A Berlin statutory-insurance patient describes their need; the agent returns the fastest routes to a specialist
appointment, each with the reason and the evidence behind every claim.

Pipeline (`fasttrack/agent.py`, `investigate()`):

1. **plan**: Nemotron Lightning splits the question into up to 5 data questions.
2. **query**: one read-only SQL per question over Zetaris Lightning (`FT_RULES.rules`, `FT_PRACTICES.practices`,
   `FT_WAITS.waits`). The SQL drafts and the web search run concurrently; the queries run one by one on the single
   JDBC connection. Every returned row gets an evidence id `E1…`.
3. **web**: Firecrawl search, then Lightning extracts only facts stated on the page; every row keeps its source URL.
   Booking portals whose terms forbid automated access are excluded (doctolib, jameda, docinsider, sanego).
4. **recall**: Meterless H-MEM returns earlier verified findings.
5. **answer**: Nemotron Ultra ranks the routes and cites evidence ids only.
6. **verify**: Lightning drops every route whose claims its cited rows don't support (`dropped` in the result).
7. **remember**: kept routes go into H-MEM with their run id and evidence.

| Part | Files |
|---|---|
| Model calls (roles, JSON parsing, Ultra fallback) | `fasttrack/llm.py` |
| Zetaris JDBC and the SQLite stand-in, SQL guard | `fasttrack/sources.py`; seed data in `data/seed/*.csv`, all SAMPLE |
| Register the CSVs in Zetaris | `zetaris/register.py` |
| H-MEM bridge (Node, tsx) and local JSONL fallback | `fasttrack/memory.py`, `meterless/bridge.ts`, vendored `meterless/hmem/src` |
| Firecrawl search and extraction | `fasttrack/web.py` |
| Web app: `/`, `/miniapp`, `/ask`, `/ask/stream` (NDJSON) | `fasttrack/app.py`, `fasttrack/static/*` |
| Telegram bot: live status edits, QR, mini app menu button | `fasttrack/telegram_bot.py` |
| `.env` loader (shell values win) | `fasttrack/env.py` |
| Containers: app, quick tunnel, bot | `Dockerfile`, `compose.yaml`, `.env.example` |

## Run

```powershell
cd C:\Tools\fasttrack-termin
git pull
docker compose up --build -d
```

```powershell
docker compose logs -f bot app
```

- Web UI: `http://127.0.0.1:8765`.
- Mini app: the bot prints `[telegram] mini app: https://<words>.trycloudflare.com/miniapp` and sets the
  Telegram menu button itself. The quick-tunnel URL changes on every restart of the `tunnel` container.
- Bot: `@FastTrackTerminBot`. QR for onboarding: `python -m fasttrack.telegram_bot --qr bot-qr.png`.
- Tests: `python -m pytest -q` (13 pass, no network needed).
- Zetaris tables: `python zetaris/register.py` registers the seed CSVs and prints row counts.

`.env` (git-ignored) holds `NVIDIA_API_KEY`, `FIRECRAWL_API_KEY`, `TELEGRAM_BOT_TOKEN`, `ZETARIS_USER`,
`ZETARIS_PASSWORD`, `ZETARIS_JDBC_JAR` (non-empty switches Zetaris on), `ZETARIS_JDBC_DIR`. Model overrides:
`FT_MODEL_PLANNER`, `FT_MODEL_SQL`, `FT_MODEL_ANSWER`, `FT_MODEL_VERIFIER`, `FT_MODEL_FALLBACK`.

## Verified state (last live run on the laptop)

- All three containers up; the bot set the mini app menu button.
- Zetaris JDBC driver loaded in the container (the SLF4J lines in the bot log come from it).
- Nemotron planner and SQL calls returned 200; Firecrawl search returned 200.
- That run was before `6e8e86d` (concurrent SQL drafts): SQL calls took 11–70 s each, one after another.

## Open, in priority order

1. **Speed check after `6e8e86d`.** `git pull`, rebuild, ask one question in the web UI, note the total time. If
   still too slow for the video, try `FT_MODEL_SQL=nvidia/nemotron-3-ultra-550b-a55b` in `.env` (untested whether
   Ultra is faster) or lower the planner's question cap in `agent.py`.
2. **End-to-end answer check.** Confirm one live run reaches answer and verify, shows route cards with "Why this
   route", and that the footer reads `source zetaris-lightning · web firecrawl-search · memory meterless-h-mem`. If
   memory shows `local-jsonl`, the H-MEM bridge failed in the container (Node/tsx); check `docker compose exec app
   ls meterless/node_modules/.bin`.
3. **Zetaris row counts.** Run `zetaris/register.py` once and check that the counts match the CSVs (rules 7,
   practices 10, waits 12). Unconfirmed so far whether the `file://` path works in Lightning.
4. **Mini app in Telegram.** Open the bot on a phone, tap the menu button, run one question, check the live
   steps and the Call/Route/Source buttons.
5. **Video.** Follow `docs/DEMO.md`. Record before the freeze.
6. **Submit** on the hackathon page with repo link, video, deck PDF and the sponsor explanation.

## Parallel agents and file ownership

Three ChatGPT agents coordinate on GitHub issue #1 and own docs only. Each commits its own file(s), then
posts "Done: <path> <sha>" on #1.

| Agent | Owns |
|---|---|
| README | `README.md`, next `docs/EXPLAINABILITY.md` |
| Deck | `docs/deck/*`, next `docs/STORY.md` |
| Submission/Demo | `docs/SUBMISSION.md`, `docs/DEMO.md`, next `docs/SPONSORS.md` |

The code (`fasttrack/`, `meterless/bridge.ts`, `zetaris/`, `tests/`, Docker files) belongs to this session. Tell
the agents on #1 when a code change alters a fact they describe.

## Rules

- Never print, log, commit or put on a command line any key, token or password. Keys live only in `.env`.
- Commit as `Andreas Krüger <AndiKrue@users.noreply.github.com>`; end commit messages with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Every source file carries `SPDX-License-Identifier: AGPL-3.0-or-later`. Licence AGPL-3.0-or-later; never edit
  `LICENSE`. `meterless/hmem/src` is vendored unmodified (Apache-2.0, see its NOTICE); do not edit it.
- No invented facts: practice and wait data are SAMPLE and labelled so; web rows always carry their URL.
- Never medical advice; emergencies point to 112, on-call service 116117.
- Stage files by name, never `git add -A`; check that `.env` and `bot-qr.png` are not staged.
- PowerShell: one command per block for the owner; no `2>$null`.
- Pull with `git pull --rebase` before every push; the doc agents push to `main` too.
