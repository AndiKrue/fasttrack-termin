<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Handoff 2 — after the hackathon deadline (28 Oct 2026)

For the Claude Code session on the laptop (`C:\Tools\fasttrack-termin`). Read fully before the first change.

## Branch rules (binding until the results call, 6 Nov 2026 16:00 UTC)

| Branch | Content | May go live (judged bot) |
|---|---|---|
| `main` + tag `hackathon-submission-2026-10-27` | the submitted state | **never push to main before 6 Nov** |
| `post-hackathon` | bug fixes of submitted features (H-MEM recall `ecb66b7`, speech Chrome fixes `221fafa`), docs | yes — the live stack runs this branch |
| `voice` | WO-FT-VOICE-01 (`docs/wo/WO-FT-VOICE-01.md`) | part A yes after host acceptance (cherry-pick to `post-hackathon`); part B after 6 Nov |
| `miniapp-ux` | plain-language evidence in the mini app (`3d12c6c` parent) | after 6 Nov |

Never `git pull` one of these branches from another: `git pull` on `post-hackathon` must pull `origin post-hackathon`
(set upstream once: `git branch -u origin/post-hackathon post-hackathon`). A pull from `main` brought the H-MEM revert
into `post-hackathon` once; `ecb66b7` restored it.

## Live stack (judged, keep it running)

- `docker compose` app + bot + tunnel on `post-hackathon`; tunnel URL in `docker compose logs bot | Select-String "mini app"`.
- Nightshift headless: scheduled task "Meterless daemon" starts `meterlessd.exe` at logon; it serves `:8088`
  (`engine\host.mjs`). Closing the Nightshift app window stops the daemon; restart with
  `Start-Process "$env:LOCALAPPDATA\Nightshift\meterlessd.exe" -WindowStyle Hidden`.
- `.env`: `METERLESS_BASE_URL=http://host.docker.internal:8088/v1`, `METERLESS_RUNTIME_TOKEN`, `METERLESS_MODEL`,
  `FT_MODEL_ANSWER`/`FT_MODEL_FALLBACK` = Ultra, `ZETARIS_JDBC_JAR=on`. If Nightshift is down: comment out
  `METERLESS_BASE_URL` and `docker compose up -d app bot` (direct NVIDIA).
- Tests of new work: second app on port 8766 and `TELEGRAM_BOT_TOKEN_TEST`; never restart the judged bot for a test.

## Tasks in order

### 1. WO-FT-VOICE-01 part A (speech that works inside Telegram)
`git checkout voice`, implement `docs/wo/WO-FT-VOICE-01.md` part A (server STT/TTS through Nightshift
`meterless/transcribe` and `meterless/speech`, `/stt`, `/tts`, MediaRecorder in the mini app, `<audio>` playback),
part B in separate commits. Host acceptance on a phone (Android and iOS) against port 8766, then cherry-pick part A
onto `post-hackathon` and redeploy app + bot.

### 2. Grok code review, recorded (Zetaris challenge criterion "Working with Space XAI's coding agents")
- Separate clone: `C:\Tools\fasttrack-review` on `post-hackathon`; open it in Cursor, agent chat, Grok model.
- Record the desktop with ffmpeg (`gdigrab`, 30 fps) into `C:\Tools\narrated\out\grok-review-<timestamp>.mp4`
  while Grok runs the review prompt in `docs/review/GROK-PROMPT.md`; stop ffmpeg with `q` (not a hard kill).
- Close private windows before recording; no tokens on screen.
- Save Grok's answer verbatim as `docs/review/GROK-REVIEW-2026-10-28.md` on `post-hackathon`. Do not edit it.
- Turn the top findings into `docs/wo/WO-FT-REVIEW-01.md` (deduplicate against "Known issues" below); implement
  only bug fixes of submitted features on `post-hackathon`, everything else on a new branch.
- The write-up states exactly what happened: "Grok (xAI) reviewed the codebase in Cursor and produced the improvement
  plan." Nothing beyond what was actually done.

### 3. Zetaris Demo Challenge video (window 29 Oct 23:45 – 5 Nov 23:45 UTC)
Script: `docs/zetaris-challenge/SCRIPT.md`. Needs the Zetaris UI shots (localhost:3000), `register.py` row counts,
the federated query, an app run, the operator's own 40–60 s, and a 10–15 s clip of the Grok review.
File name `FASTTRACK-TERMIN_DDMMYY.mp4`. Upload: https://www.dropbox.com/home/Zetaris%20Demo%20Submissions

## Known issues (from live traces, not yet fixed)

1. SQL filters `district = 'Köpenick'`, the seed has `Treptow-Köpenick` → empty results. Fix in the SQL prompt
   (list the exact district values) or with `LIKE`.
2. The rules table (`FT_RULES.rules`) is rarely queried; questions about referral rules get practice queries. Tell the
   SQL role which table answers which kind of question.
3. Through Nightshift, `chat_template_kwargs.enable_thinking=false` seems not to reach the model (long reasoning in
   extraction/verifier responses). Check the Nightshift receipts; if confirmed, ask in Help Meterless.
4. No automated test for the H-MEM bridge (the guides ask for "the test showing it works").
5. No sample mode without credentials (the guides ask for it).
6. The verifier filters but does not send unsupported routes back for one revision (the guides' "strong pattern").

## Rules

Commit as `Andreas Krüger <AndiKrue@users.noreply.github.com>`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
Stage by name; never commit `.env`, audio, video, `bot-qr.png`. SPDX header on new files. No secrets in output.
