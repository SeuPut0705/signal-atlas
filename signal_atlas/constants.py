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
    VERTICAL_AI_TECH: "AI & Tech",
    VERTICAL_FINANCE: "Finance",
    VERTICAL_LIFESTYLE_POP: "Lifestyle & Pop",
}

DEFAULT_PUBLISH_LIMIT = 12
PUBLISH_STAGES = (12, 18, 24)

TARGET_TIMEZONE = "Asia/Seoul"
PROJECT_TITLE = "Signal Atlas"
PROJECT_TAGLINE = "Automated English trend briefings for ad-funded media"

ADSENSE_SLOTS = ("top-banner", "inline-1", "inline-2", "footer")

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
