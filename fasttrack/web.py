# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Live web evidence through Firecrawl search: real practices, each fact with its source URL.

Booking portals whose terms forbid automated access are excluded from the query and dropped
from the results. Nemotron extracts only facts that appear in the page text; every extracted
row keeps the URL it came from, and the page text is never shown as our own claim.
"""

from __future__ import annotations

import os

import httpx

ENDPOINT = os.environ.get("FIRECRAWL_URL", "https://api.firecrawl.dev/v1/search")
EXCLUDED = ("doctolib.", "jameda.", "docinsider.", "sanego.")
EXTRACT = (
    "From the page texts, list medical practices relevant to the patient's need. Use only facts "
    "written in the text; leave a field null when the text does not state it. "
    'Return {"practices": [{"name": "...", "address": "...", "specialty": "...", '
    '"open_consultation": "exact wording or null", "phone": "... or null", '
    '"accepts_new_patients": "exact wording or null", "url": "source url"}]}.'
)


class FirecrawlSearch:
    name = "firecrawl-search"

    def __init__(self, key: str | None = None, timeout: float = 60):
        self.key = key or os.environ.get("FIRECRAWL_API_KEY", "")
        if not self.key:
            raise RuntimeError("FIRECRAWL_API_KEY is not set")
        self.http = httpx.Client(timeout=timeout)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        q = query + "".join(f" -site:{d}de" for d in EXCLUDED)
        r = self.http.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {self.key}"},
            json={"query": q, "limit": limit, "lang": "de", "country": "de", "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True}},
        )
        print(f"[firecrawl] search -> {r.status_code}", flush=True)
        r.raise_for_status()
        pages = []
        for item in r.json().get("data") or []:
            url = item.get("url") or (item.get("metadata") or {}).get("sourceURL") or ""
            if not url or any(d in url for d in EXCLUDED):
                continue
            pages.append({"url": url, "title": item.get("title") or "", "text": (item.get("markdown") or item.get("description") or "")[:6000]})
        return pages


def web_evidence(question: str, llm, search) -> tuple[str, list[dict]]:
    """One search query from Nemotron, then extraction; returns (query, rows with url)."""
    query = llm.json(
        "sql",
        'Write one German web search query that finds statutory-insurance specialist practices for this patient (specialty, Berlin district, "offene Sprechstunde" or "neue Patienten"). Return {"query": "..."}.',
        question,
    )["query"]
    pages = search.search(query)
    if not pages:
        return query, []
    found = llm.json(
        "verifier",
        EXTRACT,
        f"Patient need: {question}\nPages: " + "\n\n".join(f"URL: {p['url']}\nTITLE: {p['title']}\n{p['text']}" for p in pages),
        max_tokens=3000,
    )
    urls = {p["url"] for p in pages}
    return query, [p for p in found.get("practices", []) if isinstance(p, dict) and p.get("url") in urls]


def open_search():
    return FirecrawlSearch() if os.environ.get("FIRECRAWL_API_KEY") else None
