"""Project-wide constants for Signal Atlas."""

from __future__ import annotations

VERTICAL_AI_TECH = "ai_tech"
VERTICAL_FINANCE = "finance"
VERTICAL_LIFESTYLE_POP = "lifestyle_pop"

ALL_VERTICALS = (
    VERTICAL_AI_TECH,
    VERTICAL_FINANCE,
    VERTICAL_LIFESTYLE_POP,
)

VERTICAL_LABELS = {
    VERTICAL_AI_TECH: "AI Technology",
    VERTICAL_FINANCE: "Business Finance",
    VERTICAL_LIFESTYLE_POP: "Culture Media",
}

DEFAULT_PUBLISH_LIMIT = 12
PUBLISH_STAGES = (12, 18, 24)

TARGET_TIMEZONE = "Asia/Seoul"
PROJECT_TITLE = "Signal Atlas"
PROJECT_TAGLINE = "Automated English trend briefings for ad-funded media"

ADSENSE_SLOTS = ("top-banner", "inline-1", "inline-2", "footer")

DEFAULT_CATEGORY = "general"
CATEGORY_AI = "ai"
CATEGORY_TECH = "tech"
CATEGORY_FINANCE = "finance"
CATEGORY_HEALTHCARE = "healthcare"
CATEGORY_STOCKS = "stocks"
CATEGORY_STARTUP = "startup"

# Single-level taxonomy (category only)
CATEGORIES_BY_VERTICAL = {
    VERTICAL_AI_TECH: (
        CATEGORY_AI,
        CATEGORY_TECH,
        CATEGORY_FINANCE,
        CATEGORY_HEALTHCARE,
        CATEGORY_STOCKS,
        CATEGORY_STARTUP,
        DEFAULT_CATEGORY,
    ),
    VERTICAL_FINANCE: (
        CATEGORY_AI,
        CATEGORY_TECH,
        CATEGORY_FINANCE,
        CATEGORY_HEALTHCARE,
        CATEGORY_STOCKS,
        CATEGORY_STARTUP,
        DEFAULT_CATEGORY,
    ),
    VERTICAL_LIFESTYLE_POP: (
        CATEGORY_AI,
        CATEGORY_TECH,
        CATEGORY_FINANCE,
        CATEGORY_HEALTHCARE,
        CATEGORY_STOCKS,
        CATEGORY_STARTUP,
        DEFAULT_CATEGORY,
    ),
}

ALL_CATEGORIES = (
    CATEGORY_AI,
    CATEGORY_TECH,
    CATEGORY_FINANCE,
    CATEGORY_HEALTHCARE,
    CATEGORY_STOCKS,
    CATEGORY_STARTUP,
    DEFAULT_CATEGORY,
)

CATEGORY_LABELS = {
    CATEGORY_AI: "AI",
    CATEGORY_TECH: "Tech",
    CATEGORY_FINANCE: "Finance",
    CATEGORY_HEALTHCARE: "Healthcare",
    CATEGORY_STOCKS: "Stocks",
    CATEGORY_STARTUP: "Startup",
    DEFAULT_CATEGORY: "General",
}

LEGACY_CATEGORY_MAP = {
    "ai-models": CATEGORY_AI,
    "developer-tools": CATEGORY_TECH,
    "enterprise-adoption": CATEGORY_TECH,
    "startups-funding": CATEGORY_STARTUP,
    "markets-macro": CATEGORY_FINANCE,
    "fintech-payments": CATEGORY_FINANCE,
    "personal-finance": CATEGORY_FINANCE,
    "policy-regulation": CATEGORY_FINANCE,
    "company-earnings": CATEGORY_STOCKS,
    "creator-economy": CATEGORY_STARTUP,
    "streaming-entertainment": CATEGORY_TECH,
    "social-platforms": CATEGORY_TECH,
    "consumer-trends": DEFAULT_CATEGORY,
    "fandom-culture": DEFAULT_CATEGORY,
}

# Rolling conditions to unlock the next publish stage.
SCALE_RULES = {
    "days": 7,
    "duplicate_rate_max": 0.05,
    "policy_flag_rate_max": 0.01,
    "indexed_rate_min": 0.35,
}

# Safety cutoffs.
POLICY_DISABLE_RATE = 0.03
DEPLOY_FAILURE_DISABLE_COUNT = 3

MAX_PUBLISHED_HISTORY = 500
MAX_DAILY_HISTORY = 120
