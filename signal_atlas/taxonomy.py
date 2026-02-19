"""Single-level category inference for Signal Atlas."""

from __future__ import annotations

from .constants import (
    CATEGORIES_BY_VERTICAL,
    DEFAULT_CATEGORY,
    VERTICAL_AI_TECH,
    VERTICAL_FINANCE,
    VERTICAL_LIFESTYLE_POP,
)
from .utils import normalize_text


_RULES: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    VERTICAL_AI_TECH: (
        ("ai-models", ("model", "llm", "gpt", "inference", "reasoning", "multimodal")),
        ("developer-tools", ("developer", "devtool", "sdk", "api", "framework", "platform launch")),
        ("startups-funding", ("funding", "seed", "series", "valuation", "venture", "startup")),
        ("enterprise-adoption", ("enterprise", "adoption", "workflow", "copilot", "deployment")),
        ("policy-regulation", ("regulation", "compliance", "policy", "governance", "safety act")),
    ),
    VERTICAL_FINANCE: (
        ("markets-macro", ("inflation", "fed", "rates", "yield", "macro", "recession", "market outlook")),
        ("fintech-payments", ("fintech", "payment", "wallet", "neobank", "transaction", "remittance")),
        ("company-earnings", ("earnings", "guidance", "quarter", "revenue", "profit", "eps")),
        ("personal-finance", ("household", "budget", "savings", "debt", "consumer spending", "credit score")),
        ("policy-regulation", ("regulation", "central bank", "policy", "tax", "sanction")),
    ),
    VERTICAL_LIFESTYLE_POP: (
        ("creator-economy", ("creator", "influencer", "newsletter", "ugc", "monetization")),
        ("streaming-entertainment", ("streaming", "netflix", "series", "movie", "box office", "entertainment")),
        ("social-platforms", ("social platform", "instagram", "tiktok", "youtube", "algorithm", "engagement")),
        ("consumer-trends", ("trend", "shopping", "lifestyle", "wellness", "consumer behavior")),
        ("fandom-culture", ("fandom", "kpop", "anime", "community", "fanbase", "viral culture")),
    ),
}


def classify_category(vertical: str, title: str, snippet: str = "") -> str:
    """Infer a category from title/snippet with deterministic keyword rules."""
    allowed = set(CATEGORIES_BY_VERTICAL.get(vertical, (DEFAULT_CATEGORY,)))
    corpus = normalize_text(f"{title} {snippet}")

    for category, keywords in _RULES.get(vertical, ()):
        if category not in allowed:
            continue
        if any(keyword in corpus for keyword in keywords):
            return category

    return DEFAULT_CATEGORY


def classify_subcategory(vertical: str, title: str, snippet: str = "") -> str:
    """Backward-compatible alias for older call sites."""
    return classify_category(vertical, title, snippet)
