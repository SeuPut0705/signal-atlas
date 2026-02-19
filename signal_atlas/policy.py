"""Policy/safety checks for generated briefs."""

from __future__ import annotations

from .constants import VERTICAL_FINANCE
from .models import PolicyResult, TopicCandidate
from .utils import normalize_text

_EXAGGERATION_PATTERNS = (
    "guaranteed",
    "shocking",
    "you won't believe",
    "100%",
    "secret trick",
    "instant",
)

_FINANCE_ADVICE_PATTERNS = (
    "buy now",
    "sell now",
    "guaranteed return",
    "financial advice",
    "invest now",
    "double your money",
    "risk free",
)


def evaluate_policy(topic: TopicCandidate) -> PolicyResult:
    """Evaluate a topic against simple but strict safety rules."""
    norm_title = normalize_text(topic.title)
    norm_snippet = normalize_text(topic.snippet)
    merged = f"{norm_title} {norm_snippet}".strip()

    flags: list[str] = []

    if not topic.source_urls:
        flags.append("missing_source")

    if len(norm_title.split()) < 4:
        flags.append("low_substance_title")

    if topic.title.strip().isupper() and len(topic.title.strip()) > 15:
        flags.append("shouting_title")

    if any(p in merged for p in _EXAGGERATION_PATTERNS):
        flags.append("exaggerated_claim")

    if topic.vertical == VERTICAL_FINANCE and any(p in merged for p in _FINANCE_ADVICE_PATTERNS):
        flags.append("finance_investment_advice")

    blocked = any(flag in {"missing_source", "finance_investment_advice"} for flag in flags)
    score = 1.0 - (0.12 * len(flags)) - (0.4 if blocked else 0.0)
    score = max(0.0, min(1.0, round(score, 4)))

    return PolicyResult(score=score, flags=flags, blocked=blocked)
