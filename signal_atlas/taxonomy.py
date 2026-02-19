"""Single-level category inference for Signal Atlas."""

from __future__ import annotations

from .constants import (
    CATEGORY_AI,
    CATEGORY_FINANCE,
    CATEGORY_HEALTHCARE,
    CATEGORY_STOCKS,
    CATEGORY_STARTUP,
    CATEGORY_TECH,
    CATEGORIES_BY_VERTICAL,
    DEFAULT_CATEGORY,
)
from .utils import normalize_text


_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Prioritize stocks first so mixed headlines (e.g. "AI stock rally") are grouped into stocks.
    (
        CATEGORY_STOCKS,
        (
            "stock",
            "stocks",
            "share price",
            "shares",
            "nasdaq",
            "nyse",
            "s&p",
            "dow jones",
            "earnings",
            "ipo",
            "etf",
            "market rally",
        ),
    ),
    (
        CATEGORY_HEALTHCARE,
        (
            "health",
            "healthcare",
            "medical",
            "hospital",
            "biotech",
            "pharma",
            "drug",
            "fda",
            "clinical trial",
            "patient",
            "diagnosis",
        ),
    ),
    (
        CATEGORY_AI,
        (
            "ai",
            "artificial intelligence",
            "llm",
            "model",
            "gpt",
            "openai",
            "anthropic",
            "machine learning",
            "copilot",
            "inference",
            "agent",
        ),
    ),
    (
        CATEGORY_TECH,
        (
            "technology",
            "software",
            "cloud",
            "semiconductor",
            "chip",
            "developer",
            "api",
            "operating system",
            "smartphone",
            "streaming service",
            "social media",
        ),
    ),
    (
        CATEGORY_STARTUP,
        (
            "startup",
            "funding",
            "seed",
            "series a",
            "series b",
            "series c",
            "venture capital",
            "unicorn",
            "founder",
        ),
    ),
    (
        CATEGORY_FINANCE,
        (
            "finance",
            "fintech",
            "payment",
            "bank",
            "credit",
            "inflation",
            "interest rate",
            "federal reserve",
            "economy",
            "monetary policy",
            "budget",
        ),
    ),
)


def classify_category(vertical: str, title: str, snippet: str = "") -> str:
    """Infer a category from title/snippet with deterministic keyword rules."""
    allowed = set(CATEGORIES_BY_VERTICAL.get(vertical, (DEFAULT_CATEGORY,)))
    corpus = normalize_text(f"{title} {snippet}")

    for category, keywords in _RULES:
        if category not in allowed:
            continue
        if any(keyword in corpus for keyword in keywords):
            return category

    return DEFAULT_CATEGORY


def classify_subcategory(vertical: str, title: str, snippet: str = "") -> str:
    """Backward-compatible alias for older call sites."""
    return classify_category(vertical, title, snippet)
