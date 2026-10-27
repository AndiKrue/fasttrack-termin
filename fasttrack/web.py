# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Andreas Krueger
"""Live web evidence through Firecrawl search: real practices, each fact with its source URL.

Booking portals whose terms forbid automated access are excluded from the query and dropped
from the results. Nemotron extracts only facts that appear in the page text; every extracted
row keeps the URL it came from, and the page text is never shown as our own claim.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, wait

import httpx

ENDPOINT = os.environ.get("FIRECRAWL_URL", "https://api.firecrawl.dev/v1/search")
MAX_PAGES = 3
MAX_CHARS = 3000
EXTRACT_SECONDS = 20
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
            pages.append({"url": url, "title": item.get("title") or "", "text": (item.get("markdown") or item.get("description") or "")[:MAX_CHARS]})
        return pages


def _extract(question: str, llm, page: dict) -> list[dict]:
    found = llm.json("verifier", EXTRACT, f"Patient need: {question}\nURL: {page['url']}\nTITLE: {page['title']}\n{page['text']}", max_tokens=2048, think=False)
    return [p for p in found.get("practices", []) if isinstance(p, dict) and p.get("url") == page["url"]]


def web_evidence(question: str, llm, search) -> tuple[str, list[dict]]:
    """One search query from Nemotron, then extraction; returns (query, rows with url).

    Each page is extracted in its own call; after EXTRACT_SECONDS the answer goes ahead with
    the rows from the pages that are done, so a slow page never holds up the whole run.
    """
    query = llm.json(
        "sql",
        'Write one German web search query that finds statutory-insurance specialist practices for this patient (specialty, Berlin district, "offene Sprechstunde" or "neue Patienten"). Return {"query": "..."}.',
        question,
    )["query"]
    pages = [{**p, "text": p["text"][:MAX_CHARS]} for p in search.search(query, limit=MAX_PAGES)[:MAX_PAGES]]
    if not pages:
        return query, []
    pool = ThreadPoolExecutor(max_workers=len(pages))
    futures = [pool.submit(_extract, question, llm, p) for p in pages]
    done, _ = wait(futures, timeout=EXTRACT_SECONDS)
    pool.shutdown(wait=False, cancel_futures=True)
    rows = []
    for f in futures:  # page order, not completion order
        if f in done and f.exception() is None:
            rows.extend(f.result())
    return query, rows


def open_search():
    return FirecrawlSearch() if os.environ.get("FIRECRAWL_API_KEY") else None
