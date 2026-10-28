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
from pathlib import Path

import httpx

REASONING = "\n\x00REASONING\x00\n"
# Meterless Nightshift is the primary AI provider when METERLESS_BASE_URL is set (its local OpenAI-compatible
# runtime, default port 8088, NVIDIA connected in its Providers tab). Without it, the NVIDIA API is called directly.
NIGHTSHIFT = os.environ.get("METERLESS_BASE_URL", "").rstrip("/")
if NIGHTSHIFT and not NIGHTSHIFT.endswith("/v1"):
    NIGHTSHIFT += "/v1"
NVIDIA_BASE = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
BASE = NIGHTSHIFT or NVIDIA_BASE
PROVIDER = "meterless-nightshift" if NIGHTSHIFT else "nvidia-api"
SAMPLE_REPLIES = Path(__file__).resolve().parent.parent / "data" / "sample" / "replies.json"
# Under Nightshift every role asks for a meterless/* route (METERLESS_MODEL, default meterless/auto; pin a
# Nemotron-backed lane per role with FT_MODEL_*). The model Nightshift actually used is recorded per call.
_DEFAULT = _NVIDIA = {
    "planner": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "sql": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "answer": "nvidia/nemotron-3-ultra-550b-a55b",
    "verifier": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "fallback": "nvidia/nemotron-3-ultra-550b-a55b",
}
if NIGHTSHIFT:
    _DEFAULT = {role: os.environ.get("METERLESS_MODEL", "meterless/auto") for role in _DEFAULT}
MODELS = {role: os.environ.get(f"FT_MODEL_{role.upper()}", _DEFAULT[role]) for role in ("planner", "sql", "answer", "verifier")}
FALLBACK = os.environ.get("FT_MODEL_FALLBACK", _DEFAULT["fallback"])
# Lightning roles answer without a reasoning block: a SQL draft drops from ~20 s to ~1 s, and the
# verifier from 20-80 s with erratic verdicts to a few seconds. Ultra (answer) keeps reasoning.
NO_THINK = {"planner", "sql", "verifier"}


class Nemotron:
    def __init__(self, key: str | None = None, timeout: float = 120):
        if NIGHTSHIFT:
            self.key = key or os.environ.get("METERLESS_RUNTIME_TOKEN") or os.environ.get("METERLESS_TOKEN", "")
            if not self.key or self.key == "rt-local":  # rt-local is the docs' placeholder, not a token
                raise RuntimeError("METERLESS_RUNTIME_TOKEN (the Nightshift Console API key) is not set")
            self.headers = {"Authorization": f"Bearer {self.key}", "meterless-app": "fasttrack-termin", "meterless-scope": "user"}
        else:
            self.key = key or os.environ.get("NVIDIA_API_KEY", "")
            if not self.key:
                raise RuntimeError("NVIDIA_API_KEY is not set")
            self.headers = {"Authorization": f"Bearer {self.key}"}
        self.provider = PROVIDER
        self.http = httpx.Client(base_url=BASE, timeout=timeout)
        self.calls: list[dict] = []
        # Nightshift down (no connection, 5xx) -> the same call on the NVIDIA API, when a key is set.
        backup_key = os.environ.get("NVIDIA_API_KEY", "") if NIGHTSHIFT else ""
        self.backup = httpx.Client(base_url=NVIDIA_BASE, timeout=timeout) if backup_key else None
        self.backup_headers = {"Authorization": f"Bearer {backup_key}"}

    def chat(self, role: str, system: str, user: str, max_tokens: int = 2048, model: str | None = None, think: bool | None = None) -> str:
        started = time.monotonic()
        last_try = model is not None  # json() passes a model only for its last try on Ultra
        model = model or MODELS[role]
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if think is None:
            think = role not in NO_THINK
        if not think and model == MODELS[role]:  # the fallback retry keeps its reasoning
            body["chat_template_kwargs"] = {"enable_thinking": False}
        provider = self.provider
        try:
            r = self.http.post("/chat/completions", json=body, headers=self.headers)
            status = r.status_code
        except httpx.TransportError as exc:
            if self.backup is None:
                raise
            r, status = None, type(exc).__name__
        print(f"[nemotron] {role} {model} via {provider} -> {status} in {time.monotonic() - started:.1f}s", flush=True)
        if self.backup is not None and (r is None or r.status_code >= 500):
            provider, model = "nvidia-api", _NVIDIA["fallback" if last_try else role]
            r = self.backup.post("/chat/completions", json={**body, "model": model}, headers=self.backup_headers)
            print(f"[nemotron] {role} {model} via {provider} (Nightshift fallback) -> {r.status_code} in {time.monotonic() - started:.1f}s", flush=True)
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        self.calls.append(
            {
                "role": role,
                "model": model,
                "provider": provider,
                "served_model": data.get("model"),
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


class SampleLLM:
    """Recorded model replies for the demo question (FT_SAMPLE=1, or no model credentials at all).

    Nothing leaves the machine: the planner, SQL, answer and verifier replies come from
    data/sample/replies.json, the queries run on the local SQLite stand-in, and every answer
    says it is sample mode. Any question gets the recorded Köpenick knee case.
    """

    sample = True
    provider = "sample"

    def __init__(self, path: Path = SAMPLE_REPLIES):
        self.replies = json.loads(path.read_text(encoding="utf-8"))
        self.calls: list[dict] = []

    def json(self, role: str, system: str, user: str, max_tokens: int = 8192, think: bool | None = None):
        self.calls.append({"role": role, "model": "recorded", "provider": self.provider, "seconds": 0})
        if role == "sql":
            sql = self.replies["sql"].get(user.split("\n")[0], self.replies["sql_default"])
            return {"sql": sql}
        return json.loads(json.dumps(self.replies[role]))  # a fresh copy: the agent edits the routes


def open_llm():
    """Nemotron, or the recorded sample replies when FT_SAMPLE=1 or no model credentials are set."""
    if os.environ.get("FT_SAMPLE") == "1":
        return SampleLLM()
    try:
        return Nemotron()
    except RuntimeError as exc:
        print(f"[nemotron] {exc}: running in sample mode with recorded replies", flush=True)
        return SampleLLM()
