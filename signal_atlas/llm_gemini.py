"""Gemini generation client with schema validation and one-step retry."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from .models import ApprovedTopic

try:  # pragma: no cover - optional dependency.
    from google import genai  # type: ignore
except Exception:  # pragma: no cover - optional dependency.
    genai = None


class GeminiUnavailableError(RuntimeError):
    """Raised when Gemini SDK/key is unavailable."""


class GeminiGenerationError(RuntimeError):
    """Raised when Gemini response is invalid."""


@dataclass
class GeminiResult:
    payload: dict[str, Any]
    estimated_cost_krw: float
    model: str
    quality_tier: str


def _client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiUnavailableError("GEMINI_API_KEY is missing")
    if genai is None:
        raise GeminiUnavailableError("google-genai SDK is not installed")
    return genai.Client(api_key=api_key)


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        chunks: list[str] = []
        for part in parts:
            value = getattr(part, "text", None)
            if isinstance(value, str) and value.strip():
                chunks.append(value.strip())
        if chunks:
            return "\n".join(chunks)
    return ""


def _first_json_blob(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise GeminiGenerationError("No JSON object in Gemini response")
    return text[start : end + 1]


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(one).strip() for one in value if str(one).strip()]
    return []


def _normalize_faq(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for one in value:
        if not isinstance(one, dict):
            continue
        q = str(one.get("q") or "").strip()
        a = str(one.get("a") or "").strip()
        if q and a:
            rows.append({"q": q, "a": a})
    return rows


def _enforce_meta_length(text: str, min_len: int = 140, max_len: int = 160) -> str:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return ""
    if len(cleaned) < min_len:
        cleaned = f"{cleaned} Read the full breakdown, implications, and what to track next."
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip(" ,.;:") + "."
    return cleaned


def _validate_payload(payload: dict[str, Any], *, min_words: int, max_words: int, min_sources: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    for key in ("summary", "seo_title", "meta_description", "contrarian_view"):
        if not str(payload.get(key) or "").strip():
            reasons.append(f"missing:{key}")

    key_points = _normalize_list(payload.get("key_points"))
    deep_dive = _normalize_list(payload.get("deep_dive"))
    implications = _normalize_list(payload.get("implications"))
    faq = _normalize_faq(payload.get("faq"))
    sources = _normalize_list(payload.get("source_urls"))

    if len(key_points) < 4:
        reasons.append("insufficient:key_points")
    if len(deep_dive) < 2:
        reasons.append("insufficient:deep_dive")
    if len(implications) < 2:
        reasons.append("insufficient:implications")
    if len(faq) < 3:
        reasons.append("insufficient:faq")
    if len(sources) < min_sources:
        reasons.append("insufficient:sources")

    text_sections = [
        str(payload.get("summary") or ""),
        " ".join(key_points),
        " ".join(deep_dive),
        " ".join(implications),
        str(payload.get("contrarian_view") or ""),
        " ".join(f"{row['q']} {row['a']}" for row in faq),
    ]
    words = len(" ".join(text_sections).split())
    if words < min_words:
        reasons.append("insufficient:word_count")
    if words > max_words:
        reasons.append("excessive:word_count")

    meta_description = str(payload.get("meta_description") or "")
    if len(meta_description) < 140 or len(meta_description) > 160:
        reasons.append("invalid:meta_description_length")

    return len(reasons) == 0, reasons


def _usage_cost_krw(response: Any, quality_tier: str) -> float:
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    if prompt_tokens <= 0 and output_tokens <= 0:
        return 220.0 if quality_tier == "premium" else 120.0
    multiplier = 1.0 if quality_tier == "premium" else 0.65
    return round((prompt_tokens * 0.015 + output_tokens * 0.06) * multiplier, 2)


def _schema_prompt(
    topic: ApprovedTopic,
    *,
    min_words: int,
    max_words: int,
    min_sources: int,
    quality_tier: str,
) -> str:
    source_lines = "\n".join(f"- {url}" for url in topic.source_urls[:8])
    source_meta_lines = "\n".join(
        f"- title={meta.title or '(missing)'} | site={meta.site_name or '(missing)'} | url={meta.url}"
        for meta in topic.source_meta[:8]
    )
    return f"""
You are a senior editorial analyst writing high-quality English trend briefings for an ad-funded media site.

Constraints:
- Quality tier: {quality_tier}
- Language: English
- Total content length target: {min_words}-{max_words} words
- Minimum sources in output: {min_sources}
- Finance category must stay informational, no investment advice.
- Use only data inferable from the provided sources.

Topic:
- Category: {topic.category}
- Title: {topic.title}
- Snippet: {topic.snippet}

Source URLs:
{source_lines}

Source metadata:
{source_meta_lines}

Output strictly valid JSON with this schema:
{{
  "seo_title": "string",
  "meta_description": "140-160 chars",
  "summary": "string",
  "key_points": ["string", "... min 4"],
  "deep_dive": ["paragraph string", "... min 2"],
  "implications": ["paragraph string", "... min 2"],
  "contrarian_view": "string",
  "faq": [{{"q":"string","a":"string"}}, "... min 3"],
  "hero_image_alt": "string",
  "source_urls": ["url", "... min {min_sources}"]
}}

No markdown. JSON only.
""".strip()


def _ask_gemini(
    topic: ApprovedTopic,
    *,
    model: str,
    min_words: int,
    max_words: int,
    min_sources: int,
    quality_tier: str,
    remediation: str = "",
) -> tuple[dict[str, Any], float]:
    prompt = _schema_prompt(
        topic,
        min_words=min_words,
        max_words=max_words,
        min_sources=min_sources,
        quality_tier=quality_tier,
    )
    if remediation:
        prompt = f"{prompt}\n\nFix these issues in this generation attempt:\n{remediation}"

    client = _client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.35 if quality_tier == "premium" else 0.5,
        },
    )

    text = _extract_text(response)
    if not text:
        raise GeminiGenerationError("Gemini returned empty response text")
    blob = _first_json_blob(text)
    payload = json.loads(blob)
    if not isinstance(payload, dict):
        raise GeminiGenerationError("Gemini payload is not a JSON object")

    payload["meta_description"] = _enforce_meta_length(str(payload.get("meta_description") or ""))
    valid, reasons = _validate_payload(payload, min_words=min_words, max_words=max_words, min_sources=min_sources)
    if not valid:
        raise GeminiGenerationError("invalid_payload:" + ",".join(reasons))
    return payload, _usage_cost_krw(response, quality_tier)


def generate_structured_brief(
    topic: ApprovedTopic,
    *,
    model: str,
    quality_tier: str = "premium",
    min_words: int = 900,
    max_words: int = 1300,
    min_sources: int = 3,
) -> GeminiResult:
    """Generate structured content via Gemini, retrying once on quality/schema failures."""
    try:
        payload, cost = _ask_gemini(
            topic,
            model=model,
            min_words=min_words,
            max_words=max_words,
            min_sources=min_sources,
            quality_tier=quality_tier,
        )
        return GeminiResult(payload=payload, estimated_cost_krw=cost, model=model, quality_tier=quality_tier)
    except GeminiUnavailableError:
        raise
    except Exception as first_exc:
        remediation = str(first_exc)
        payload, cost = _ask_gemini(
            topic,
            model=model,
            min_words=min_words,
            max_words=max_words,
            min_sources=min_sources,
            quality_tier=quality_tier,
            remediation=remediation,
        )
        return GeminiResult(payload=payload, estimated_cost_krw=cost, model=model, quality_tier=quality_tier)
