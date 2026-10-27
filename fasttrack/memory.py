# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Memory of verified findings, with provenance, recalled on the next question.

`HMemStore` talks to Meterless H-MEM through a small Node bridge (`meterless/bridge.ts`, run with tsx,
JSON on stdin/stdout). `LocalStore` keeps the same records in a JSONL file so the agent works
without Node. Every record carries the run id and the evidence it came from.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class LocalStore:
    name = "local-jsonl"

    def __init__(self, path: Path | None = None):
        self.path = path or ROOT / "runs" / "memory.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def remember(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        if not self.path.exists():
            return []
        words = {w for w in query.lower().split() if len(w) > 3}
        scored = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            text = json.dumps(record, ensure_ascii=False).lower()
            score = sum(w in text for w in words)
            if score:
                scored.append((score, record))
        return [r for _, r in sorted(scored, key=lambda x: -x[0])[:limit]]


class HMemStore:
    name = "meterless-h-mem"

    def __init__(self, bridge: Path | None = None):
        self.bridge = bridge or ROOT / "meterless" / "bridge.ts"
        self.tsx = shutil.which("tsx", path=str(ROOT / "meterless" / "node_modules" / ".bin"))
        if not self.bridge.exists() or not self.tsx:
            raise FileNotFoundError("H-MEM bridge needs Node and `npm install` in meterless/")

    def _call(self, payload: dict) -> dict:
        done = subprocess.run(
            [self.tsx, str(self.bridge)],
            cwd=ROOT,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if done.returncode:
            raise RuntimeError(f"H-MEM bridge failed: {done.stderr.strip()[-300:]}")
        return json.loads(done.stdout or "{}")

    def remember(self, record: dict) -> None:
        self._call({"op": "remember", "record": record})

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        return self._call({"op": "recall", "query": query, "limit": limit}).get("records", [])


def open_memory():
    """H-MEM unless FT_MEMORY=local or the bridge is missing."""
    if os.environ.get("FT_MEMORY", "hmem") != "local":
        try:
            return HMemStore()
        except FileNotFoundError:
            pass
    return LocalStore()


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
