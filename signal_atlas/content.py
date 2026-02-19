"""Content generation layer for markdown/json artifacts."""

from __future__ import annotations

import os
import urllib.parse
from typing import Any

from .constants import ADSENSE_SLOTS, CATEGORY_LABELS, CATEGORY_STOCKS, VERTICAL_FINANCE
from .models import ApprovedTopic, GeneratedBrief
from .utils import slugify

MIN_WORDS = 900
MAX_WORDS = 1300
MIN_SOURCES = 3
MIN_FAQ = 3


def _title_keywords(title: str, max_items: int = 6) -> list[str]:
    words = [w.strip(" ,.!?:;()[]{}\"'") for w in title.split()]
    words = [w for w in words if len(w) >= 4]
    if not words:
        return ["trend", "market", "signal", "timing"]
    uniq: list[str] = []
    for word in words:
        lw = word.lower()
        if lw not in [u.lower() for u in uniq]:
            uniq.append(word)
        if len(uniq) >= max_items:
            break
    while len(uniq) < 4:
        uniq.append(["trend", "market", "signal", "timing"][len(uniq)])
    return uniq


def _meta_description(seed: str) -> str:
    text = " ".join(seed.split()).strip()
    if len(text) < 140:
        text = (
            f"{text} Read the full briefing for key data points, competitive implications, "
            "and practical signals to monitor next."
        ).strip()
    if len(text) > 160:
        text = text[:159].rstrip(" ,.;:") + "."
    return text


def _reading_time(word_count: int) -> int:
    return max(1, round(word_count / 220))


def _fallback_hero_image(category: str) -> str:
    safe = slugify(category) or "general"
    return f"/assets/covers/{safe}.svg"


def _find_hero_image(topic: ApprovedTopic) -> str:
    for meta in topic.source_meta:
        if meta.image:
            return meta.image
    return _fallback_hero_image(topic.category)


def _ensure_min_sources(topic: ApprovedTopic, min_sources: int = MIN_SOURCES) -> list[str]:
    ordered: list[str] = []
    for url in topic.source_urls:
        one = str(url or "").strip()
        if one and one not in ordered:
            ordered.append(one)
    for meta in topic.source_meta:
        one = str(meta.url or "").strip()
        if one and one not in ordered:
            ordered.append(one)

    if len(ordered) < min_sources:
        query = urllib.parse.quote_plus(topic.title)
        candidates = [
            f"https://news.google.com/rss/search?q={query}",
            f"https://www.bing.com/news/search?q={query}",
            f"https://duckduckgo.com/?q={query}&ia=news",
        ]
        for url in candidates:
            if url not in ordered:
                ordered.append(url)
            if len(ordered) >= min_sources:
                break

    return ordered[:8]


def _template_paragraph(topic: ApprovedTopic, *, angle: str, idx: int, keywords: list[str]) -> str:
    category = CATEGORY_LABELS.get(topic.category, topic.category)
    k1 = keywords[idx % len(keywords)]
    k2 = keywords[(idx + 1) % len(keywords)]
    k3 = keywords[(idx + 2) % len(keywords)]
    return (
        f"{angle} in {category} is shifting from isolated announcements to coordinated execution across product, "
        f"distribution, and monetization. Teams that track {k1} and {k2} together usually detect trend inflection "
        f"earlier than teams that watch headline volume alone. A practical reading of this signal is that operators "
        f"need tighter feedback loops between market observation and roadmap decisions, because {k3} can move from "
        "experimentation to budget line item within a single planning cycle. This creates asymmetric upside for "
        "organizations that ship fast but preserve evidence discipline, attribution clarity, and channel-level "
        "measurement. The near-term opportunity is not only participation in demand, but also better narrative "
        "positioning that compounds trust with each follow-up release."
    )


def _template_structured(topic: ApprovedTopic, quality_tier: str) -> dict[str, Any]:
    keywords = _title_keywords(topic.title)
    category_label = CATEGORY_LABELS.get(topic.category, topic.category)

    summary = (
        f"{topic.title} signals a meaningful shift in {category_label}. This briefing explains what changed, why the "
        "signal matters now, and which operational metrics indicate whether momentum is strengthening or fading."
    )

    key_points = [
        f"Momentum is concentrated around {keywords[0]} and cross-channel distribution efficiency.",
        f"Execution risk is increasingly linked to {keywords[1]} and governance readiness.",
        f"Competitive pressure is visible in how quickly peers are repositioning around {keywords[2]}.",
        f"Near-term upside depends on translating {keywords[3]} into measurable product or revenue outcomes.",
        "Decision quality improves when teams combine trend observation with source-level evidence checks.",
    ]

    deep_dive = [
        _template_paragraph(topic, angle="Deep-dive", idx=0, keywords=keywords),
        _template_paragraph(topic, angle="Market structure", idx=1, keywords=keywords),
        _template_paragraph(topic, angle="Execution timing", idx=2, keywords=keywords),
    ]
    implications = [
        _template_paragraph(topic, angle="Commercial implication", idx=3, keywords=keywords),
        _template_paragraph(topic, angle="Operational implication", idx=4, keywords=keywords),
    ]
    contrarian_view = (
        "A contrarian read is that headline momentum can overstate durable demand. If follow-through metrics stall, "
        "teams that overcommit early may face cost drag and narrative reset. The better hedge is phased execution "
        "with explicit validation gates, so strategic conviction is updated by evidence rather than hype cycles."
    )
    faq = [
        {
            "q": "What changed most recently?",
            "a": "The signal shifted from isolated events to a broader operating pattern validated across multiple sources.",
        },
        {
            "q": "What should operators track next?",
            "a": "Track follow-up releases, distribution velocity, and whether adoption signals remain consistent over two cycles.",
        },
        {
            "q": "What is the main risk?",
            "a": "The core risk is confusing short-lived attention spikes with durable structural demand.",
        },
    ]

    tone_hint = "premium analytical depth" if quality_tier == "premium" else "balanced concise depth"
    return {
        "seo_title": f"{topic.title} | Signal Atlas",
        "meta_description": _meta_description(f"{summary} This {tone_hint} briefing outlines implications and next signals."),
        "summary": summary,
        "key_points": key_points,
        "deep_dive": deep_dive,
        "implications": implications,
        "contrarian_view": contrarian_view,
        "faq": faq,
        "hero_image_alt": f"{topic.title} trend coverage",
        "source_urls": [],
    }


def _normalize_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for one in value:
        line = " ".join(str(one).split()).strip()
        if line:
            out.append(line)
    return out


def _normalize_faq(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for one in value:
        if not isinstance(one, dict):
            continue
        q = " ".join(str(one.get("q") or "").split()).strip()
        a = " ".join(str(one.get("a") or "").split()).strip()
        if q and a:
            out.append({"q": q, "a": a})
    return out


def _payload_word_count(payload: dict[str, Any]) -> int:
    chunks: list[str] = []
    chunks.append(str(payload.get("summary") or ""))
    chunks.extend(_normalize_text_list(payload.get("key_points")))
    chunks.extend(_normalize_text_list(payload.get("deep_dive")))
    chunks.extend(_normalize_text_list(payload.get("implications")))
    chunks.append(str(payload.get("contrarian_view") or ""))
    for row in _normalize_faq(payload.get("faq")):
        chunks.append(f"{row['q']} {row['a']}")
    return len(" ".join(chunks).split())


def _apply_word_bounds(payload: dict[str, Any], topic: ApprovedTopic, *, min_words: int, max_words: int) -> dict[str, Any]:
    payload["deep_dive"] = _normalize_text_list(payload.get("deep_dive"))
    payload["implications"] = _normalize_text_list(payload.get("implications"))
    keywords = _title_keywords(topic.title)

    while _payload_word_count(payload) < min_words:
        bucket = "deep_dive" if len(payload["deep_dive"]) <= len(payload["implications"]) + 1 else "implications"
        idx = len(payload[bucket]) + 5
        payload[bucket].append(_template_paragraph(topic, angle="Supplementary analysis", idx=idx, keywords=keywords))
        if len(payload["deep_dive"]) + len(payload["implications"]) > 10:
            break

    while _payload_word_count(payload) > max_words:
        if len(payload["deep_dive"]) > 2:
            payload["deep_dive"].pop()
        elif len(payload["implications"]) > 2:
            payload["implications"].pop()
        else:
            break

    return payload


def _render_markdown(payload: dict[str, Any], disclaimer: str) -> str:
    sources_md = "\n".join([f"- {url}" for url in payload["source_urls"]])
    faq_rows = [f"- **{row['q']}** {row['a']}" for row in payload["faq"]]

    lines: list[str] = [
        f"# {payload['title']}",
        "",
        f"Category: {payload['category_label']}",
        "",
        "[AD_SLOT:top-banner]",
        "",
    ]
    if disclaimer:
        lines.extend([f"> {disclaimer}", ""])
    lines.extend(
        [
            "## TL;DR",
            payload["summary"],
            "",
            "## Key Data Points",
            *[f"- {point}" for point in payload["key_points"]],
            "",
            "[AD_SLOT:inline-1]",
            "",
            "## Deep Dive",
            *payload["deep_dive"],
            "",
            "## Implications",
            *payload["implications"],
            "",
            "## Contrarian View",
            payload["contrarian_view"],
            "",
            "## FAQ",
            *faq_rows,
            "",
            "## Sources",
            sources_md or "- Source unavailable",
            "",
            "[AD_SLOT:inline-2]",
            "",
            "[AD_SLOT:footer]",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def _json_ld_stub(payload: dict[str, Any], topic: ApprovedTopic) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": payload["title"],
        "description": payload["meta_description"],
        "articleSection": payload["category_label"],
        "inLanguage": "en",
        "keywords": ", ".join(_title_keywords(topic.title)),
        "isAccessibleForFree": True,
        "datePublished": topic.discovered_at,
        "dateModified": topic.discovered_at,
        "mainEntityOfPage": "",
    }


def _normalize_payload(
    raw: dict[str, Any],
    topic: ApprovedTopic,
    *,
    sources: list[str],
    generation_engine: str,
    generation_model: str,
    generation_cost_krw: float,
    quality_tier: str,
    min_words: int,
    max_words: int,
) -> dict[str, Any]:
    category_label = CATEGORY_LABELS.get(topic.category, topic.category)

    payload = {
        "slug": slugify(topic.title),
        "title": topic.title,
        "vertical": topic.vertical,
        "category": topic.category,
        "category_label": category_label,
        "seo_title": " ".join(str(raw.get("seo_title") or "").split()).strip() or f"{topic.title} | Signal Atlas",
        "meta_description": _meta_description(str(raw.get("meta_description") or raw.get("summary") or topic.title)),
        "summary": " ".join(str(raw.get("summary") or "").split()).strip() or topic.title,
        "key_points": _normalize_text_list(raw.get("key_points")),
        "deep_dive": _normalize_text_list(raw.get("deep_dive")),
        "implications": _normalize_text_list(raw.get("implications")),
        "contrarian_view": " ".join(str(raw.get("contrarian_view") or "").split()).strip(),
        "faq": _normalize_faq(raw.get("faq")),
        "faq_extended": _normalize_faq(raw.get("faq")),
        "source_urls": sources,
        "hero_image_url": str(raw.get("hero_image_url") or _find_hero_image(topic)).strip(),
        "hero_image_alt": " ".join(str(raw.get("hero_image_alt") or f"{topic.title} trend coverage").split()).strip(),
        "disclaimer": "",
        "ad_slots": list(ADSENSE_SLOTS),
        "confidence_score": topic.confidence_score,
        "policy_score": topic.policy_score,
        "policy_flags": topic.policy_flags,
        "generation_engine": generation_engine,
        "generation_model": generation_model,
        "quality_tier": quality_tier,
        "generation_cost_krw": round(float(generation_cost_krw), 2),
    }

    if len(payload["key_points"]) < 4:
        payload["key_points"].extend(_template_structured(topic, quality_tier)["key_points"][: 4 - len(payload["key_points"])])
    if len(payload["deep_dive"]) < 2:
        payload["deep_dive"].extend(_template_structured(topic, quality_tier)["deep_dive"][: 2 - len(payload["deep_dive"])])
    if len(payload["implications"]) < 2:
        payload["implications"].extend(_template_structured(topic, quality_tier)["implications"][: 2 - len(payload["implications"])])
    if not payload["contrarian_view"]:
        payload["contrarian_view"] = _template_structured(topic, quality_tier)["contrarian_view"]
    if len(payload["faq"]) < MIN_FAQ:
        payload["faq"].extend(_template_structured(topic, quality_tier)["faq"][: MIN_FAQ - len(payload["faq"])])
        payload["faq_extended"] = payload["faq"]

    payload = _apply_word_bounds(payload, topic, min_words=min_words, max_words=max_words)
    word_count = _payload_word_count(payload)
    payload["word_count"] = word_count
    payload["reading_time"] = _reading_time(word_count)
    payload["json_ld"] = _json_ld_stub(payload, topic)

    if topic.vertical == VERTICAL_FINANCE or topic.category == CATEGORY_STOCKS:
        payload["disclaimer"] = "This content is for informational purposes only and is not investment, legal, or tax advice."

    return payload


def build_generated_brief(
    topic: ApprovedTopic,
    *,
    generation_engine: str | None = None,
    quality_tier: str | None = None,
    gemini_model: str | None = None,
    min_words: int = MIN_WORDS,
    max_words: int = MAX_WORDS,
    min_sources: int = MIN_SOURCES,
) -> GeneratedBrief:
    """Create one markdown + JSON briefing from an approved topic."""
    engine_requested = (generation_engine or os.getenv("GENERATION_ENGINE") or "gemini").strip().lower()
    quality = (quality_tier or os.getenv("QUALITY_TIER") or "premium").strip().lower()
    model = gemini_model or os.getenv("GEMINI_MODEL") or "gemini-2.5-pro"
    if quality not in {"premium", "balanced"}:
        quality = "premium"
    if engine_requested not in {"gemini", "template"}:
        engine_requested = "gemini"

    sources = _ensure_min_sources(topic, min_sources=min_sources)
    raw: dict[str, Any] = {}
    engine_used = engine_requested
    generation_model = "template-default"
    generation_cost = 0.0

    if engine_requested == "gemini":
        try:
            from .llm_gemini import GeminiGenerationError, GeminiUnavailableError, generate_structured_brief

            result = generate_structured_brief(
                topic,
                model=model,
                quality_tier=quality,
                min_words=min_words,
                max_words=max_words,
                min_sources=min_sources,
            )
            raw = result.payload
            generation_model = result.model
            generation_cost = result.estimated_cost_krw
        except Exception:
            # Any gemini failure triggers template fallback to keep publishing fully automated.
            engine_used = "template-fallback"
            raw = _template_structured(topic, quality)
    else:
        raw = _template_structured(topic, quality)

    payload = _normalize_payload(
        raw,
        topic,
        sources=sources,
        generation_engine=engine_used,
        generation_model=generation_model,
        generation_cost_krw=generation_cost,
        quality_tier=quality,
        min_words=min_words,
        max_words=max_words,
    )

    markdown = _render_markdown(payload, payload.get("disclaimer", ""))
    word_count = int(payload.get("word_count") or len(markdown.split()))
    payload["word_count"] = word_count
    payload["reading_time"] = _reading_time(word_count)

    return GeneratedBrief(
        topic=topic,
        slug=str(payload["slug"]),
        markdown=markdown,
        payload=payload,
        word_count=word_count,
    )
