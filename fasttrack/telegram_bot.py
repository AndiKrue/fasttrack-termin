# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Telegram bot: ask in chat, watch the agent work in one live-edited status message, get the routes.

Run:  python -m fasttrack.telegram_bot            (long polling)
QR:   python -m fasttrack.telegram_bot --qr qr.png (onboarding code for https://t.me/<bot>)
Env:  TELEGRAM_BOT_TOKEN, NVIDIA_API_KEY (+ the app's Zetaris/Firecrawl vars), FT_MINIAPP_URL (optional).
The token is never printed; errors are redacted before they are shown or logged.
"""

from __future__ import annotations

import html
import os
import sys
import threading
import time
from urllib.parse import quote

import httpx

from .agent import investigate

LIMIT = 4000  # Telegram allows 4096 characters per message; leave room for markup
WELCOME = (
    "<b>FastTrack Termin</b>\n"
    "Tell me which specialist you need, where you live in Berlin and whether you have a referral. "
    "I find the fastest route to an appointment and show the reason and the evidence for each step.\n\n"
    "Practices and waiting times in the demo database are SAMPLE data; web results link their source.\n"
    "Not medical advice. In an emergency call 112."
)
STEPS = [
    ("plan", "Planning (Nemotron)"),
    ("query", "Querying Zetaris"),
    ("web", "Web search (Firecrawl)"),
    ("recall", "Memory (H-MEM)"),
    ("verify", "Verifying"),
]


class Telegram:
    def __init__(self, token: str, client: httpx.Client | None = None):
        self.token = token
        self.http = client or httpx.Client(timeout=40)

    def redact(self, text: str) -> str:
        return str(text).replace(self.token, "[token]") if self.token else str(text)

    def call(self, method: str, **params):
        for attempt in range(5):
            try:
                r = self.http.post(f"https://api.telegram.org/bot{self.token}/{method}", json=params)
                data = r.json()
            except Exception as exc:  # network error: back off and retry
                print(f"[telegram] {method} failed: {self.redact(type(exc).__name__)}", flush=True)
                time.sleep(min(2**attempt, 30))
                continue
            if data.get("ok"):
                return data.get("result")
            retry = (data.get("parameters") or {}).get("retry_after")
            if r.status_code == 429 and retry:
                time.sleep(float(retry))
                continue
            raise RuntimeError(self.redact(f"{method}: {data.get('description')}"))
        raise RuntimeError(f"{method}: gave up after retries")


def checklist(done: dict) -> str:
    lines = ["<b>Working on your question</b>"]
    for key, label in STEPS:
        info = done.get(key)
        mark = "✅" if info is not None else "⏳"
        lines.append(f"{mark} {html.escape(label)}{' — ' + html.escape(info) if info else ''}")
    return "\n".join(lines)


def describe(step: dict) -> str:
    kind = step.get("step")
    if step.get("error"):
        return "skipped"
    if kind == "plan":
        return f"{len(step.get('questions', []))} questions"
    if kind == "query":
        q = step.get("queries", [])
        return f"{len(q)} queries, {sum(len(x.get('evidence', [])) for x in q)} rows"
    if kind == "web":
        return f"{step.get('practices', 0)} practices"
    if kind == "recall":
        return f"{step.get('records', 0)} records"
    if kind == "verify":
        return f"kept {step.get('kept', 0)}, dropped {step.get('dropped', 0)}"
    return ""


def render(result: dict) -> list[str]:
    """Routes as HTML-escaped messages, each under the Telegram size limit."""
    e = html.escape
    blocks = []
    for i, r in enumerate(result.get("routes", []), 1):
        lines = [f"<b>{i}. {e(str(r.get('route', '')))}</b>"]
        if r.get("expected_days") is not None:
            lines.append(f"Expected: about {e(str(r['expected_days']))} days")
        lines.append(f"Why: {e(str(r.get('why', '')))}")
        for eid in r.get("evidence", []):
            ev = result.get("evidence", {}).get(eid) or {}
            row = ev.get("row") or {}
            name = row.get("name")
            line = f"• {e(eid)}" + (f" {e(str(name))}" if name else "")
            if row.get("phone"):
                line += f"\n  Phone: {e(str(row['phone']))}"
            if row.get("address"):
                line += f"\n  Route: https://www.openstreetmap.org/directions?to={quote(str(row['address']))}"
            if ev.get("url"):
                line += f"\n  Source: {e(str(ev['url']))}"
            lines.append(line)
        blocks.append("\n".join(lines))
    for c in result.get("caveats", []):
        blocks.append(f"<i>Note: {e(str(c))}</i>")
    if not result.get("routes"):
        blocks.insert(0, "No route could be backed by evidence this time. Try naming the specialty and your district.")
    blocks.append("Not medical advice. In an emergency call 112.")
    messages, current = [], ""
    for b in blocks:
        while len(b) > LIMIT:  # one oversized block: hard split
            messages.append(b[:LIMIT])
            b = b[LIMIT:]
        if len(current) + len(b) + 2 > LIMIT:
            messages.append(current)
            current = ""
        current = f"{current}\n\n{b}" if current else b
    if current:
        messages.append(current)
    return messages


class Bot:
    def __init__(self, tg: Telegram, llm, ask=investigate):
        self.tg, self.llm, self.ask = tg, llm, ask
        self.busy: set[int] = set()
        self.lock = threading.Lock()

    def handle(self, update: dict) -> threading.Thread | None:
        msg = update.get("message") or {}
        text, chat = msg.get("text"), (msg.get("chat") or {}).get("id")
        if not text or chat is None:
            return None
        if text.startswith("/start"):
            params = {"chat_id": chat, "text": WELCOME, "parse_mode": "HTML"}
            url = os.environ.get("FT_MINIAPP_URL")
            if url:
                params["reply_markup"] = {"inline_keyboard": [[{"text": "Open FastTrack app", "web_app": {"url": url}}]]}
            self.tg.call("sendMessage", **params)
            return None
        with self.lock:
            if chat in self.busy:
                self.tg.call("sendMessage", chat_id=chat, text="Still working on your last question, one moment.")
                return None
            self.busy.add(chat)
        worker = threading.Thread(target=self.answer, args=(chat, text[:2000]), daemon=True)
        worker.start()
        return worker

    def answer(self, chat: int, question: str) -> None:
        done: dict = {}
        try:
            status = self.tg.call("sendMessage", chat_id=chat, text=checklist(done), parse_mode="HTML")
            mid = status["message_id"]

            def on_step(step: dict) -> None:
                done[step.get("step")] = describe(step)
                self.tg.call("editMessageText", chat_id=chat, message_id=mid, text=checklist(done), parse_mode="HTML")

            result = self.ask(question, self.llm, on_step=on_step)
            for text in render(result):
                self.tg.call("sendMessage", chat_id=chat, text=text, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as exc:
            print(f"[telegram] question failed: {self.tg.redact(exc)}", flush=True)
            try:
                self.tg.call("sendMessage", chat_id=chat, text="Sorry, that failed. Please try again.")
            except Exception:
                pass
        finally:
            with self.lock:
                self.busy.discard(chat)

    def poll(self) -> None:
        offset = None
        while True:
            try:
                updates = self.tg.call("getUpdates", timeout=30, offset=offset, allowed_updates=["message"]) or []
            except RuntimeError as exc:
                print(f"[telegram] poll: {self.tg.redact(exc)}", flush=True)
                time.sleep(5)
                continue
            for u in updates:
                offset = u["update_id"] + 1
                self.handle(u)


def write_qr(tg: Telegram, path: str) -> str:
    link = f"https://t.me/{tg.call('getMe')['username']}"
    try:
        import segno  # optional, pure Python
    except ImportError:
        print(f"Bot link: {link}\nFor a PNG QR code: pip install segno, then rerun with --qr {path}")
        return link
    segno.make(link, error="m").save(path, scale=10, border=2)
    print(f"QR code for {link} written to {path}")
    return link


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN is not set")
    tg = Telegram(token)
    if argv[:1] == ["--qr"]:
        write_qr(tg, argv[1] if len(argv) > 1 else "fasttrack-bot-qr.png")
        return
    from .llm import Nemotron

    bot = Bot(tg, Nemotron())
    print(f"FastTrack bot polling as @{tg.call('getMe')['username']}", flush=True)
    bot.poll()


if __name__ == "__main__":
    main()
