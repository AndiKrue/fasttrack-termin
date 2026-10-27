# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Nemotron through the NVIDIA API (OpenAI-compatible), one model per role.

planner  - decides which questions to ask the sources (Lightning 30B, fast)
sql      - turns each question into one read-only SELECT over the federated schema
answer   - ranks the routes and explains why, citing evidence ids only (Ultra 550B)
verifier - checks every claim against the cited rows and strikes the unsupported ones
"""

from __future__ import annotations

import json
import os
import re
import time

import httpx

REASONING = "\n\x00REASONING\x00\n"
BASE = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODELS = {
    "planner": os.environ.get("FT_MODEL_PLANNER", "nvidia/nemotron-3.5-lightning-30b-a3b"),
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
        print(f"[nemotron] {role} {MODELS[role]} -> {r.status_code} in {time.monotonic() - started:.1f}s", flush=True)
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
        choice = data["choices"][0]
        message = choice.get("message") or {}
        self.last_finish = choice.get("finish_reason")
        # Reasoning models may answer after a long reasoning block or, when cut, only inside it.
        return (message.get("content") or "") + REASONING + (message.get("reasoning_content") or "")

    def json(self, role: str, system: str, user: str, max_tokens: int = 8192):
        system = system + "\nReply with one JSON object only, no prose."
        try:
            return parse_json(self.chat(role, system, user, max_tokens))
        except ValueError:
            text = self.chat(role, system + " Do not think aloud. Output the JSON immediately.", user, max_tokens)
            try:
                return parse_json(text)
            except ValueError:
                raise ValueError(f"model reply contained no JSON (finish_reason={self.last_finish})") from None


def parse_json(text: str):
    """The last complete JSON object in the answer; falls back to the reasoning text."""
    decoder = json.JSONDecoder()
    for part in text.split(REASONING):
        part = re.sub(r"<think>.*?</think>", "", part, flags=re.DOTALL)
        found = None
        for i, ch in enumerate(part):
            if ch in "{[":
                try:
                    value, _ = decoder.raw_decode(part, i)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    found = value
        if found is not None:
            return found
    raise ValueError("model reply contained no JSON")
