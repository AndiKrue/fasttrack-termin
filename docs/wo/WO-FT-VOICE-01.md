# WO-FT-VOICE-01 — Speech in and out through Meterless Nightshift

| Field | Value |
|---|---|
| Repo | `fasttrack-termin` (`C:\Tools\fasttrack-termin`) |
| Branch | `voice` (from `post-hackathon`). Never merge into `main` before 6 Nov 2026: `main` and tag `hackathon-submission-2026-10-27` are the judged state. |
| Deploy | Part A (deliverables 1, 2, 4, 5, 6): a fix of the submitted Speak / Read aloud buttons (commit 0d32a7f, before the deadline) that do not work inside Telegram's WebView. May go to the live stack via `post-hackathon` once accepted on the test port. Part B (deliverable 3, bot voice messages): new feature, not in the submission; live only after the results call (6 Nov 2026, 16:00 UTC). |
| Executor | Claude Code on the laptop (has the running stack, Nightshift and a phone for Telegram tests) |
| Readiness | READY |

## 0. Problem

Speech input and read-aloud use the browser Web Speech API. Inside Telegram the mini app runs in Telegram's
WebView: Android WebViews expose `webkitSpeechRecognition` without a working service (the Speak button appears,
nothing is transcribed) and often have no TTS voice (Read aloud is silent). The chat bot has no voice at all.

## 1. Architecture

Speech runs server-side through Meterless Nightshift, the app's AI provider. Its runtime already lists the routes
`meterless/transcribe` and `meterless/speech` (check `GET /v1/models` with the runtime token first; use the
concrete ids it returns).

```
Telegram voice message ─▶ bot ─▶ download (getFile) ─▶ llm.transcribe() ─▶ Nightshift /v1/audio/transcriptions
mini app MediaRecorder ─▶ POST /stt ───────────────▶ llm.transcribe() ─┘
mini app / web Read aloud ─▶ POST /tts ─▶ llm.speak() ─▶ Nightshift /v1/audio/speech ─▶ audio/ogg|mp3 ─▶ <audio>
```

- One client for all model traffic: add `transcribe(audio: bytes, mime: str, lang: str | None) -> str` and
  `speak(text: str, voice: str | None) -> bytes` to `fasttrack/llm.py` (`Nemotron`), reusing `BASE`, `self.headers`
  (Bearer runtime token, `meterless-app`, `meterless-scope: user`) and the call log (`provider`, `served_model`,
  seconds). Routes from env: `FT_STT_MODEL` (default `meterless/transcribe`), `FT_TTS_MODEL` (default
  `meterless/speech`), `FT_TTS_VOICE` (optional).
- Without Nightshift (`METERLESS_BASE_URL` unset) `transcribe`/`speak` raise a clear `RuntimeError`; the endpoints
  answer 503 `{"error": "speech needs Meterless Nightshift"}` and the UI falls back to the browser API.
- Browser Web Speech stays as fallback in the web app (desktop Chrome/Edge work).

## 2. Deliverables

1. `fasttrack/llm.py`: `transcribe()` (multipart `file`, `model`, optional `language`) and `speak()` (JSON
   `model`, `input`, `voice`, `response_format: "mp3"`), both with a 60 s timeout and an entry in `self.calls`.
2. `fasttrack/app.py`:
   - `POST /stt`: body = raw audio (`Content-Type` audio/webm, audio/ogg or audio/mp4), max 2 MB and 60 s;
     returns `{"text": "..."}`. Reject other types with 415, larger bodies with 413.
   - `POST /tts`: JSON `{"text": "..."}`, max 1500 characters; returns `audio/mpeg`.
   - Never log audio, text bodies or tokens.
3. **Part B, after 6 Nov.** `fasttrack/telegram_bot.py`: handle `message.voice` (and `message.audio`): `getFile` → download from
   `https://api.telegram.org/file/bot<token>/<path>` (token redacted in every error) → `transcribe` → reply
   "I heard: <text>" → run the normal investigation with the live status message. Max 60 s voice; longer gets a
   polite refusal. `/start` text mentions "send a voice message".
4. `fasttrack/static/miniapp.html`: Speak button records with `navigator.mediaDevices.getUserMedia` +
   `MediaRecorder` (prefer `audio/webm;codecs=opus`, else `audio/mp4`), tap to stop, auto-stop at 30 s, upload to
   `/stt`, put the text into the question box (never auto-submit). Read aloud fetches `/tts` and plays it through
   one shared `<audio>` element; a second press stops. On 503 fall back to the Web Speech code that exists now.
   Show errors in the button text (the pattern from commit 221fafa).
5. `fasttrack/static/app.js`: same server path when `/config` says `speech: true`; otherwise keep the browser API.
   `/config` gains `speech: bool` (true when Nightshift is configured).
6. `.env.example`: `FT_STT_MODEL`, `FT_TTS_MODEL`, `FT_TTS_VOICE` with comments; no values that are secrets.
7. README section "Speech" on branch `voice` only (README on `main` stays frozen).

## 3. Tests (unittest, no network)

- `llm.transcribe` / `speak` against `httpx.MockTransport`: correct URL (`/v1/audio/transcriptions`,
  `/v1/audio/speech`), headers (`meterless-app`), multipart field names, call log entry.
- `/stt`: 415 on wrong type, 413 over limit, 503 without Nightshift, 200 with a faked client.
- `/tts`: 400 on empty text, length cap, 200 returns audio bytes with the faked client.
- Bot: a fake `voice` update → `getFile` + download mocked → transcribe called → investigation started; the token
  never appears in any raised message.
- `python -m pytest -q` green; `node --check` on `app.js` and the mini app script.

## 4. Host acceptance (on the laptop, Claude Code runs these)

1. `GET /v1/models` lists the STT and TTS routes; set `FT_STT_MODEL` / `FT_TTS_MODEL` to them.
2. `curl` one transcription and one speech request against Nightshift directly.
3. `git checkout voice; docker compose up --build -d app bot` **only on a second port or after 6 Nov**: for testing
   before 6 Nov run a second app container on port 8766 (`FT_PORT=8766`, no tunnel, no bot) and a separate test bot
   token (`TELEGRAM_BOT_TOKEN_TEST`), so the judged bot is untouched.
4. Phone: voice message to the test bot → transcription → routes. Mini app on the test port via a second quick
   tunnel → Speak and Read aloud work on Android and iOS.

## 5. Branch flow

1. Build part A and part B on `voice`, part B behind its own commits.
2. After part A passes host acceptance on the test port: cherry-pick only the part A commits onto `post-hackathon`,
   push, `docker compose up --build -d app bot` on the live stack.
3. Part B stays on `voice` until 6 Nov.

## 6. Rules

- Commit as `Andreas Krüger <AndiKrue@users.noreply.github.com>`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Stage files by name; never commit `.env`, audio files or `bot-qr.png`.
- No new Python dependency (httpx multipart is enough); no new JS dependency.
- Keep every existing behaviour: text questions, browser speech fallback, the judged bot.
- Closeout: `docs/wo/CLOSEOUT-WO-FT-VOICE-01.md` with what was verified on the phone and what was not.
