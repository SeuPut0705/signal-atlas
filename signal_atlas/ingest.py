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
from html.parser import HTMLParser
from typing import Callable

from .constants import ALL_VERTICALS, DEFAULT_CATEGORY, VERTICAL_AI_TECH, VERTICAL_FINANCE, VERTICAL_LIFESTYLE_POP
from .models import SourceMeta, TopicCandidate
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


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}
        self._capture_title = False
        self.page_title = ""

    def handle_starttag(self, tag: str, attrs):
        attrs_dict = {str(k).lower(): str(v) for k, v in attrs if k and v}
        if tag.lower() == "meta":
            key = (attrs_dict.get("property") or attrs_dict.get("name") or "").lower()
            content = attrs_dict.get("content", "")
            if key and content and key not in self.meta:
                self.meta[key] = content.strip()
        elif tag.lower() == "title":
            self._capture_title = True

    def handle_data(self, data: str):
        if self._capture_title and not self.page_title:
            self.page_title = data.strip()

    def handle_endtag(self, tag: str):
        if tag.lower() == "title":
            self._capture_title = False


@dataclass
class IngestMeta:
    source_failures: int
    used_fallback: bool


def _clean_html_text(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_html.sub(" ", html.unescape(text or ""))).strip()


def _fetch_source_meta(url: str, timeout_sec: int = 6) -> SourceMeta:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (SignalAtlas/1.0)",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read(220_000)
    except Exception:
        return SourceMeta(url=url)

    text = raw.decode("utf-8", errors="ignore")
    parser = _MetaParser()
    try:
        parser.feed(text)
    except Exception:
        return SourceMeta(url=url)

    meta = parser.meta
    title = meta.get("og:title") or meta.get("twitter:title") or parser.page_title
    description = meta.get("og:description") or meta.get("description") or meta.get("twitter:description") or ""
    image = meta.get("og:image") or meta.get("twitter:image") or ""
    site_name = meta.get("og:site_name") or ""
    return SourceMeta(
        url=url,
        title=_clean_html_text(title),
        description=_clean_html_text(description),
        image=image.strip(),
        site_name=_clean_html_text(site_name),
    )


def _candidate_source_urls(rows: list[dict], current_url: str, max_urls: int = 5) -> list[str]:
    ordered = [current_url] if current_url else []
    for row in rows:
        url = str(row.get("url") or "").strip()
        if url and url not in ordered:
            ordered.append(url)
        if len(ordered) >= max_urls:
            break
    return ordered


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
        source_meta_cache: dict[str, SourceMeta] = {}
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

                source_urls = _candidate_source_urls(rows, url, max_urls=5)
                discovered_at = isoformat(now)
                snippet = str(row.get("snippet") or "").strip()
                source_meta: list[SourceMeta] = []
                for one_url in source_urls[:3]:
                    if one_url not in source_meta_cache:
                        source_meta_cache[one_url] = _fetch_source_meta(one_url)
                    source_meta.append(source_meta_cache[one_url])

                candidates.append(
                    TopicCandidate(
                        id=candidate_id,
                        vertical=vertical,
                        title=title,
                        source_urls=source_urls,
                        discovered_at=discovered_at,
                        category=DEFAULT_CATEGORY,
                        snippet=snippet,
                        source_meta=source_meta,
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
                        source_urls=[
                            f"https://example.com/fallback/{vertical}/{idx}",
                            f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(title)}",
                            f"https://www.bing.com/news/search?q={urllib.parse.quote_plus(title)}",
                        ],
                        discovered_at=isoformat(now),
                        category=DEFAULT_CATEGORY,
                        snippet="Fallback topic used due to temporary source instability.",
                        source_meta=[
                            SourceMeta(
                                url=f"https://example.com/fallback/{vertical}/{idx}",
                                title=title,
                                description="Fallback source used due to temporary ingestion issues.",
                                image="",
                                site_name="Signal Atlas Fallback",
                            )
                        ],
                    )
                )
                if len(candidates) >= max_candidates:
                    break

        return candidates[:max_candidates], IngestMeta(source_failures=failures, used_fallback=used_fallback)
