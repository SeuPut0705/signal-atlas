"""Content generation layer for markdown/json artifacts."""

from __future__ import annotations

from .constants import ADSENSE_SLOTS, VERTICAL_FINANCE, VERTICAL_LABELS
from .models import ApprovedTopic, GeneratedBrief
from .utils import slugify


def _title_keywords(title: str, max_items: int = 4) -> list[str]:
    words = [w.strip(" ,.!?:;()[]{}\"'") for w in title.split()]
    words = [w for w in words if len(w) >= 4]
    if not words:
        return ["trend", "market", "signal"]
    uniq: list[str] = []
    for word in words:
        lw = word.lower()
        if lw not in [u.lower() for u in uniq]:
            uniq.append(word)
        if len(uniq) >= max_items:
            break
    return uniq


def build_generated_brief(topic: ApprovedTopic) -> GeneratedBrief:
    """Create one markdown + JSON briefing from an approved topic."""
    slug = slugify(topic.title)
    keywords = _title_keywords(topic.title)

    summary = (
        f"{topic.title}. This briefing captures the core signal, why it matters right now, "
        "and what to watch next."
    )

    key_points = [
        f"The main trend centers on {keywords[0]} and related ecosystem shifts.",
        f"Recent momentum suggests {keywords[1] if len(keywords) > 1 else 'continued demand'} in the near term.",
        f"Operators should monitor {keywords[2] if len(keywords) > 2 else 'execution risk'} over the next cycle.",
    ]

    faq = [
        {
            "q": "What changed this week?",
            "a": "The underlying signal moved from isolated updates to a broader pattern with clear adoption pressure.",
        },
        {
            "q": "What should readers track next?",
            "a": "Watch follow-up announcements, distribution metrics, and whether sentiment remains consistent over 7-14 days.",
        },
    ]

    disclaimer = (
        "This content is for informational purposes only and is not investment, legal, or tax advice."
        if topic.vertical == VERTICAL_FINANCE
        else ""
    )

    sources_md = "\n".join([f"- {url}" for url in topic.source_urls])

    md_lines = [
        f"# {topic.title}",
        "",
        f"Vertical: {VERTICAL_LABELS.get(topic.vertical, topic.vertical)}",
        "",
        "[AD_SLOT:top-banner]",
        "",
    ]

    if disclaimer:
        md_lines.extend([f"> {disclaimer}", ""])

    md_lines.extend(
        [
            "## TL;DR",
            summary,
            "",
            "## Key Points",
            *[f"- {point}" for point in key_points],
            "",
            "[AD_SLOT:inline-1]",
            "",
            "## Why It Matters",
            "This trend has cross-platform implications for reach, monetization, and competitive positioning.",
            "",
            "## Sources",
            sources_md or "- Source unavailable",
            "",
            "## FAQ",
            f"- **{faq[0]['q']}** {faq[0]['a']}",
            f"- **{faq[1]['q']}** {faq[1]['a']}",
            "",
            "[AD_SLOT:inline-2]",
            "",
            "[AD_SLOT:footer]",
        ]
    )

    markdown = "\n".join(md_lines).strip() + "\n"
    word_count = len(markdown.split())

    payload = {
        "slug": slug,
        "title": topic.title,
        "vertical": topic.vertical,
        "summary": summary,
        "key_points": key_points,
        "faq": faq,
        "source_urls": topic.source_urls,
        "disclaimer": disclaimer,
        "ad_slots": list(ADSENSE_SLOTS),
        "confidence_score": topic.confidence_score,
        "policy_score": topic.policy_score,
        "policy_flags": topic.policy_flags,
    }

    return GeneratedBrief(topic=topic, slug=slug, markdown=markdown, payload=payload, word_count=word_count)
