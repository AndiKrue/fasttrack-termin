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
# Meterless Nightshift is the primary AI provider when METERLESS_BASE_URL is set (its local OpenAI-compatible
# runtime, default port 8088, NVIDIA connected in its Providers tab). Without it, the NVIDIA API is called directly.
NIGHTSHIFT = os.environ.get("METERLESS_BASE_URL", "").rstrip("/")
if NIGHTSHIFT and not NIGHTSHIFT.endswith("/v1"):
    NIGHTSHIFT += "/v1"
BASE = NIGHTSHIFT or os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
PROVIDER = "meterless-nightshift" if NIGHTSHIFT else "nvidia-api"
MODELS = {
    "planner": os.environ.get("FT_MODEL_PLANNER", "nvidia/nemotron-3.5-lightning-30b-a3b"),
    "sql": os.environ.get("FT_MODEL_SQL", "nvidia/nemotron-3.5-lightning-30b-a3b"),
    "answer": os.environ.get("FT_MODEL_ANSWER", "nvidia/nemotron-3-ultra-550b-a55b"),
    "verifier": os.environ.get("FT_MODEL_VERIFIER", "nvidia/nemotron-3.5-lightning-30b-a3b"),
}
FALLBACK = os.environ.get("FT_MODEL_FALLBACK", "nvidia/nemotron-3-ultra-550b-a55b")
# Lightning roles answer without a reasoning block: a SQL draft drops from ~20 s to ~1 s, and the
# verifier from 20-80 s with erratic verdicts to a few seconds. Ultra (answer) keeps reasoning.
NO_THINK = {"planner", "sql", "verifier"}


class Nemotron:
    def __init__(self, key: str | None = None, timeout: float = 120):
        if NIGHTSHIFT:
            self.key = key or os.environ.get("METERLESS_TOKEN", "")
            if not self.key or self.key == "rt-local":  # rt-local is the docs' placeholder, not a token
                raise RuntimeError("METERLESS_TOKEN (the Nightshift runtime token) is not set")
            self.headers = {"Authorization": f"Bearer {self.key}", "meterless-app": "fasttrack-termin", "meterless-scope": "user"}
        else:
            self.key = key or os.environ.get("NVIDIA_API_KEY", "")
            if not self.key:
                raise RuntimeError("NVIDIA_API_KEY is not set")
            self.headers = {"Authorization": f"Bearer {self.key}"}
        self.provider = PROVIDER
        self.http = httpx.Client(base_url=BASE, timeout=timeout)
        self.calls: list[dict] = []

    def chat(self, role: str, system: str, user: str, max_tokens: int = 2048, model: str | None = None, think: bool | None = None) -> str:
        started = time.monotonic()
        model = model or MODELS[role]
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if think is None:
            think = role not in NO_THINK
        if not think and model != FALLBACK:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        r = self.http.post("/chat/completions", json=body, headers=self.headers)
        print(f"[nemotron] {role} {model} via {self.provider} -> {r.status_code} in {time.monotonic() - started:.1f}s", flush=True)
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        self.calls.append(
            {
                "role": role,
                "model": model,
                "provider": self.provider,
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

    def json(self, role: str, system: str, user: str, max_tokens: int = 8192, think: bool | None = None):
        system = system + "\nReply with one JSON object only, no prose."
        try:
            return parse_json(self.chat(role, system, user, max_tokens, think=think))
        except ValueError:
            text = self.chat(role, system + " Do not think aloud. Output the JSON immediately.", user, max_tokens, think=think)
            try:
                return parse_json(text)
            except ValueError:
                pass
        if MODELS[role] != FALLBACK:  # a reasoning model that keeps thinking aloud: one last try on Ultra
            print(f"[nemotron] {role}: no JSON twice, falling back to {FALLBACK}", flush=True)
            try:
                return parse_json(self.chat(role, system + " Output the JSON immediately.", user, max_tokens, model=FALLBACK))
            except ValueError:
                pass
        raise ValueError(f"model reply contained no JSON (finish_reason={self.last_finish})")


def parse_json(text: str):
    """The last complete JSON object in the answer; falls back to the reasoning text."""
    decoder = json.JSONDecoder()
    for part in text.split(REASONING):
        part = re.sub(r"<think>.*?</think>", "", part, flags=re.DOTALL)
        found, i = None, 0
        while i < len(part):
            if part[i] in "{[":
                try:
                    value, end = decoder.raw_decode(part, i)
                except json.JSONDecodeError:
                    i += 1
                    continue
                if isinstance(value, dict):
                    found = value
                i = end  # skip the object, so a nested dict never replaces its parent
                continue
            i += 1
        if found is not None:
            return found
    raise ValueError("model reply contained no JSON")
