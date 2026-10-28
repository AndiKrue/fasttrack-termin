# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""DRAFT (docs/wo/WO-FT-ASK-01.md): who may send a question to /ask behind the public tunnel.

Off unless FT_ASK_AUTH=on, so nothing changes until the owner decides. When on, a request passes
with valid Telegram mini app initData (signed by one of our bots, at most a day old) or with the
shared secret FT_ASK_SECRET in X-FT-Key. The Telegram chat bot calls the agent in-process and is
not affected.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import parse_qsl

MAX_AGE_S = 24 * 3600
BOT_TOKENS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN_TEST")


def telegram_ok(init_data: str, token: str, now: float | None = None) -> bool:
    """Telegram's check for Web App initData: HMAC-SHA256 with a key derived from the bot token."""
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    got = fields.pop("hash", "")
    if not got or not token:
        return False
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), got):
        return False
    try:
        age = (now or time.time()) - int(fields.get("auth_date", ""))
    except ValueError:
        return False
    return -60 <= age <= MAX_AGE_S


def allowed(headers) -> bool:
    if os.environ.get("FT_ASK_AUTH", "off") != "on":
        return True
    init_data = headers.get("X-Telegram-Init-Data") or ""
    if init_data and any(telegram_ok(init_data, os.environ.get(name, "")) for name in BOT_TOKENS):
        return True
    secret = os.environ.get("FT_ASK_SECRET", "")
    return bool(secret) and hmac.compare_digest((headers.get("X-FT-Key") or "").encode(), secret.encode())
