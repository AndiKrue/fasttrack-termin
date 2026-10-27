# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Nemotron through the NVIDIA API (OpenAI-compatible), one model per role.

planner  - decides which questions to ask the sources (largest model, reasoning on)
sql      - turns each question into one read-only SELECT over the federated schema
answer   - ranks the routes and explains why, citing evidence ids only
verifier - checks every claim against the cited rows and strikes the unsupported ones
"""

from __future__ import annotations

import json
import os
import re
import time

import httpx

BASE = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODELS = {
    "planner": os.environ.get("FT_MODEL_PLANNER", "nvidia/nemotron-3-ultra-550b-a55b"),
    "sql": os.environ.get("FT_MODEL_SQL", "nvidia/nemotron-3.5-lightning-30b-a3b"),
    "answer": os.environ.get("FT_MODEL_ANSWER", "nvidia/nemotron-3-ultra-550b-a55b"),
    "verifier": os.environ.get("FT_MODEL_VERIFIER", "nvidia/nemotron-3.5-lightning-30b-a3b"),
}


class Nemotron:
    def __init__(self, key: str | None = None, timeout: float = 120):
        self.key = key or os.environ.get("NVIDIA_API_KEY", "")
        if not self.key:
            raise RuntimeError("NVIDIA_API_KEY is not set")
        self.http = httpx.Client(base_url=BASE, timeout=timeout)
        self.calls: list[dict] = []

    def chat(self, role: str, system: str, user: str, max_tokens: int = 2048) -> str:
        started = time.monotonic()
        body = {
            "model": MODELS[role],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        r = self.http.post("/chat/completions", json=body, headers={"Authorization": f"Bearer {self.key}"})
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        self.calls.append(
            {
                "role": role,
                "model": MODELS[role],
                "seconds": round(time.monotonic() - started, 2),
                "tokens_in": usage.get("prompt_tokens"),
                "tokens_out": usage.get("completion_tokens"),
            }
        )
        return data["choices"][0]["message"].get("content") or ""

    def json(self, role: str, system: str, user: str, max_tokens: int = 2048):
        return parse_json(self.chat(role, system + "\nReply with JSON only.", user, max_tokens))


def parse_json(text: str):
    """The last JSON object or array in a reply, ignoring reasoning text and code fences."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("model reply contained no JSON")
