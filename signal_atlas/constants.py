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
    VERTICAL_AI_TECH: "AI & Technology",
    VERTICAL_FINANCE: "Business & Finance",
    VERTICAL_LIFESTYLE_POP: "Culture & Media",
}

DEFAULT_PUBLISH_LIMIT = 12
PUBLISH_STAGES = (12, 18, 24)

TARGET_TIMEZONE = "Asia/Seoul"
PROJECT_TITLE = "Signal Atlas"
PROJECT_TAGLINE = "Automated English trend briefings for ad-funded media"

ADSENSE_SLOTS = ("top-banner", "inline-1", "inline-2", "footer")

DEFAULT_SUBCATEGORY = "general"

# Two-level taxonomy (major category -> subcategory)
SUBCATEGORIES_BY_VERTICAL = {
    VERTICAL_AI_TECH: (
        "ai-models",
        "developer-tools",
        "startups-funding",
        "enterprise-adoption",
        "policy-regulation",
        DEFAULT_SUBCATEGORY,
    ),
    VERTICAL_FINANCE: (
        "markets-macro",
        "fintech-payments",
        "company-earnings",
        "personal-finance",
        "policy-regulation",
        DEFAULT_SUBCATEGORY,
    ),
    VERTICAL_LIFESTYLE_POP: (
        "creator-economy",
        "streaming-entertainment",
        "social-platforms",
        "consumer-trends",
        "fandom-culture",
        DEFAULT_SUBCATEGORY,
    ),
}

SUBCATEGORY_LABELS = {
    "ai-models": "AI Models",
    "developer-tools": "Developer Tools",
    "startups-funding": "Startups & Funding",
    "enterprise-adoption": "Enterprise Adoption",
    "policy-regulation": "Policy & Regulation",
    "markets-macro": "Markets & Macro",
    "fintech-payments": "Fintech & Payments",
    "company-earnings": "Company Earnings",
    "personal-finance": "Personal Finance",
    "creator-economy": "Creator Economy",
    "streaming-entertainment": "Streaming & Entertainment",
    "social-platforms": "Social Platforms",
    "consumer-trends": "Consumer Trends",
    "fandom-culture": "Fandom & Culture",
    DEFAULT_SUBCATEGORY: "General",
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
