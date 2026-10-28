# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Nemotron through the NVIDIA API (OpenAI-compatible), one model per role.

planner  - decides which questions to ask the sources (Lightning 30B, fast)
sql      - turns each question into one read-only SELECT over the federated schema
answer   - ranks the routes and explains why, citing evidence ids only (Ultra 550B)
verifier - checks every claim against the cited rows and strikes the unsupported ones
"""

from __future__ import annotations

import base64
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
# Under Nightshift every role asks for a meterless/* route (METERLESS_MODEL, default meterless/auto; pin a
# Nemotron-backed lane per role with FT_MODEL_*). The model Nightshift actually used is recorded per call.
_DEFAULT = {
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
# Speech through Nightshift. Transcription: POST /v1/meterless/transcribe (base64 JSON; its voice-asr
# engine decodes WAV only, so the browser sends 16 kHz mono WAV). Speech output: the OpenAI route
# /v1/audio/speech; builds that serve speech only as a narrate job answer 404, and the UI falls back.
STT_MODEL = os.environ.get("FT_STT_MODEL") or "meterless/transcribe"
TTS_MODEL = os.environ.get("FT_TTS_MODEL") or "meterless/speech"
TTS_VOICE = os.environ.get("FT_TTS_VOICE", "")
SPEECH_TIMEOUT = 60
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
        if not think and model == MODELS[role]:  # the fallback retry keeps its reasoning
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

    def _log_speech(self, role: str, model: str, started: float, served: str | None = None) -> None:
        self.calls.append({"role": role, "model": model, "provider": self.provider, "served_model": served,
                           "seconds": round(time.monotonic() - started, 2), "tokens_in": None, "tokens_out": None})

    def transcribe(self, audio: bytes, mime: str, lang: str | None = None) -> str:
        """Audio (16 kHz WAV works on every Nightshift build) -> text. Neither audio nor text is logged."""
        if not NIGHTSHIFT:
            raise RuntimeError("speech needs Meterless Nightshift")
        started = time.monotonic()
        ext = {"audio/wav": "wav", "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a"}.get(mime, "wav")
        body = {"model": STT_MODEL, "audio_base64": base64.b64encode(audio).decode(), "filename": f"speech.{ext}"}
        if lang:
            body["language"] = lang
        r = self.http.post("/meterless/transcribe", json=body, headers=self.headers, timeout=SPEECH_TIMEOUT)
        print(f"[nemotron] stt {STT_MODEL} via {self.provider} -> {r.status_code} in {time.monotonic() - started:.1f}s", flush=True)
        if r.status_code in (404, 503):
            raise RuntimeError("transcription is not available on Meterless Nightshift right now")
        r.raise_for_status()
        data = r.json()
        self._log_speech("stt", STT_MODEL, started, data.get("lane") or data.get("source"))
        return str(data.get("text") or "").strip()

    def speak(self, text: str, voice: str | None = None) -> bytes:
        """Text -> MP3 bytes through /v1/audio/speech."""
        if not NIGHTSHIFT:
            raise RuntimeError("speech needs Meterless Nightshift")
        started = time.monotonic()
        body = {"model": TTS_MODEL, "input": text, "response_format": "mp3"}
        if voice or TTS_VOICE:
            body["voice"] = voice or TTS_VOICE
        r = self.http.post("/audio/speech", json=body, headers=self.headers, timeout=SPEECH_TIMEOUT)
        print(f"[nemotron] tts {TTS_MODEL} via {self.provider} -> {r.status_code} in {time.monotonic() - started:.1f}s", flush=True)
        if r.status_code in (404, 503):
            raise RuntimeError("speech output is not available on Meterless Nightshift right now")
        r.raise_for_status()
        self._log_speech("tts", TTS_MODEL, started, r.headers.get("meterless-served-model"))
        return r.content

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
