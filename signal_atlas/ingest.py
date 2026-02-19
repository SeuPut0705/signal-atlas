"""Ingestion layer: collects trend candidates from low-cost public feeds."""

from __future__ import annotations

import html
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .constants import ALL_VERTICALS, VERTICAL_AI_TECH, VERTICAL_FINANCE, VERTICAL_LIFESTYLE_POP
from .models import TopicCandidate
from .utils import isoformat, stable_hash

GOOGLE_NEWS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

VERTICAL_QUERIES = {
    VERTICAL_AI_TECH: [
        "artificial intelligence startup funding",
        "open source ai release",
        "developer tools platform launch",
    ],
    VERTICAL_FINANCE: [
        "global markets inflation policy",
        "fintech earnings guidance",
        "consumer spending outlook",
    ],
    VERTICAL_LIFESTYLE_POP: [
        "streaming platform culture trend",
        "creator economy social platform",
        "celebrity media release",
    ],
}

FALLBACK_TOPICS = {
    VERTICAL_AI_TECH: [
        "Why enterprise teams are standardizing AI copilots in 2026",
        "Open models vs closed models: what changed this quarter",
        "The hidden cost of AI feature shipping velocity",
    ],
    VERTICAL_FINANCE: [
        "How inflation expectations are reshaping household budgets",
        "What quarterly earnings trends imply for growth sectors",
        "Why payment apps are racing to become financial hubs",
    ],
    VERTICAL_LIFESTYLE_POP: [
        "How short-form video trends are changing brand launches",
        "Why fandom communities now drive entertainment discovery",
        "The return of long-form storytelling in creator media",
    ],
}

_strip_html = re.compile(r"<[^>]+>")


@dataclass
class IngestMeta:
    source_failures: int
    used_fallback: bool


def _clean_html_text(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_html.sub(" ", html.unescape(text or ""))).strip()


def fetch_google_news_query(query: str, timeout_sec: int = 8) -> list[dict]:
    """Fetch a single Google News RSS query."""
    encoded = urllib.parse.quote_plus(query)
    url = GOOGLE_NEWS_TEMPLATE.format(query=encoded)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (SignalAtlas/1.0)",
            "Accept": "application/rss+xml, application/xml;q=0.9,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    out: list[dict] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = _clean_html_text(item.findtext("description") or "")
        pub_date = (item.findtext("pubDate") or "").strip()
        if not title or not link:
            continue
        out.append(
            {
                "title": title,
                "url": link,
                "snippet": description,
                "published_at": pub_date,
            }
        )
    return out


class Ingestor:
    """Fetches candidates per vertical with fallback safety."""

    def __init__(self, fetch_query: Callable[[str], list[dict]] | None = None):
        self.fetch_query = fetch_query or fetch_google_news_query

    def collect(
        self,
        vertical: str,
        now: datetime,
        max_candidates: int = 60,
    ) -> tuple[list[TopicCandidate], IngestMeta]:
        if vertical not in ALL_VERTICALS:
            raise ValueError(f"Unsupported vertical: {vertical}")

        failures = 0
        used_fallback = False
        seen: set[str] = set()
        candidates: list[TopicCandidate] = []

        for query in VERTICAL_QUERIES[vertical]:
            try:
                rows = self.fetch_query(query)
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, ValueError):
                failures += 1
                continue

            for row in rows[:20]:
                title = str(row.get("title") or "").strip()
                url = str(row.get("url") or "").strip()
                if not title:
                    continue

                candidate_id = stable_hash(f"{vertical}|{title}|{url}", n=24)
                if candidate_id in seen:
                    continue
                seen.add(candidate_id)

                source_urls = [url] if url else []
                discovered_at = isoformat(now)
                snippet = str(row.get("snippet") or "").strip()

                candidates.append(
                    TopicCandidate(
                        id=candidate_id,
                        vertical=vertical,
                        title=title,
                        source_urls=source_urls,
                        discovered_at=discovered_at,
                        snippet=snippet,
                    )
                )
                if len(candidates) >= max_candidates:
                    break

        min_required = max(4, max_candidates // 5)
        if len(candidates) < min_required:
            used_fallback = True
            for idx, title in enumerate(FALLBACK_TOPICS[vertical], start=1):
                candidate_id = stable_hash(f"fallback|{vertical}|{title}", n=24)
                if candidate_id in seen:
                    continue
                seen.add(candidate_id)
                candidates.append(
                    TopicCandidate(
                        id=candidate_id,
                        vertical=vertical,
                        title=title,
                        source_urls=[f"https://example.com/fallback/{vertical}/{idx}"],
                        discovered_at=isoformat(now),
                        snippet="Fallback topic used due to temporary source instability.",
                    )
                )
                if len(candidates) >= max_candidates:
                    break

        return candidates[:max_candidates], IngestMeta(source_failures=failures, used_fallback=used_fallback)
