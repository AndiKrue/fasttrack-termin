<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Review prompt for Grok (xAI) in Cursor

You are reviewing FastTrack Termin, an agent that finds the fastest route to a specialist appointment for statutory-insurance patients in Berlin and shows the evidence behind every claim. Stack: Python app (fasttrack/), Zetaris Lightning over JDBC as the data layer (fasttrack/sources.py, zetaris/register.py, data/seed/*.csv), NVIDIA Nemotron through Meterless Nightshift (fasttrack/llm.py), Meterless H-MEM memory via a TypeScript bridge (fasttrack/memory.py, meterless/bridge.ts), Firecrawl web evidence (fasttrack/web.py), the agent loop (fasttrack/agent.py), a web UI and Telegram mini app (fasttrack/static/), a Telegram bot (fasttrack/telegram_bot.py), Docker Compose.

Do a code review of this repository and produce an improvement plan. For each finding give: file and line, what is wrong or weak, why it matters for patients or for reliability, and a concrete fix. Rank by impact. Cover in particular:
1. How the agent uses the three Zetaris sources (rules, practices, waits): does the generated SQL match the data (column values, district names), is the rules table actually used, what makes queries come back empty?
2. Agent architecture: is there a real feedback loop between answer and verifier, or only a filter? Propose the smallest revision loop.
3. Memory: does H-MEM recall actually return earlier findings for similar questions?
4. Robustness: timeouts, retries, fallbacks when Zetaris, Nightshift or Firecrawl are down; a sample mode without credentials.
5. Security and privacy: SQL guard, secrets handling, what reaches the logs.
6. UX and accessibility of the web UI and the Telegram mini app (speech, plain-language evidence, German users).
7. Tests: what is untested that should be.
End with the five changes you would make first, each small enough for one work order.
