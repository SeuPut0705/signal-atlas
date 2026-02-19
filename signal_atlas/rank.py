"""Deduplication and ranking for topic approval."""

from __future__ import annotations

import math
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, Iterable

from .models import ApprovedTopic, PolicyResult, TopicCandidate
from .policy import evaluate_policy
from .taxonomy import classify_category
from .utils import dedupe_hash, normalize_text


@dataclass
class ApprovalStats:
    candidate_count: int
    duplicate_count: int
    policy_flag_count: int
    blocked_count: int


def _trigram_vector(text: str, dim: int = 256) -> dict[int, float]:
    norm = normalize_text(text)
    padded = f"  {norm}  "
    vec: dict[int, float] = {}
    for idx in range(len(padded) - 2):
        tri = padded[idx : idx + 3]
        bucket = hash(tri) % dim
        vec[bucket] = vec.get(bucket, 0.0) + 1.0
    return vec


def _cosine_similarity(a: dict[int, float], b: dict[int, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a).intersection(b)
    dot = sum(a[i] * b[i] for i in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _is_near_duplicate(title: str, other_title: str) -> bool:
    ratio = SequenceMatcher(a=normalize_text(title), b=normalize_text(other_title)).ratio()
    if ratio >= 0.9:
        return True

    emb_sim = _cosine_similarity(_trigram_vector(title), _trigram_vector(other_title))
    return emb_sim >= 0.86


def _confidence_score(topic: TopicCandidate, policy: PolicyResult) -> float:
    src_bonus = min(0.3, 0.1 * len(topic.source_urls))
    snippet_bonus = 0.1 if len(topic.snippet.strip()) >= 40 else 0.0
    raw = 0.45 + src_bonus + snippet_bonus + (policy.score * 0.15)
    return round(max(0.0, min(1.0, raw)), 4)


def approve_topics(
    candidates: Iterable[TopicCandidate],
    history_rows: Iterable[dict],
    max_count: int,
    policy_eval: Callable[[TopicCandidate], PolicyResult] = evaluate_policy,
) -> tuple[list[ApprovedTopic], ApprovalStats]:
    """Filter candidates into approved topics with quality/safety controls."""
    history_titles = [str(row.get("title") or "") for row in history_rows if row.get("title")]
    history_hashes = {str(row.get("dedupe_hash") or "") for row in history_rows if row.get("dedupe_hash")}

    candidate_list = list(candidates)
    approved: list[ApprovedTopic] = []

    duplicate_count = 0
    policy_flag_count = 0
    blocked_count = 0

    for candidate in candidate_list:
        d_hash = dedupe_hash(candidate.title)

        duplicate_hit = False
        if d_hash in history_hashes:
            duplicate_hit = True
        else:
            for old_title in history_titles[-220:]:
                if _is_near_duplicate(candidate.title, old_title):
                    duplicate_hit = True
                    break

        if duplicate_hit:
            duplicate_count += 1
            continue

        policy = policy_eval(candidate)
        if policy.flags:
            policy_flag_count += 1
        if policy.blocked:
            blocked_count += 1
            continue

        conf = _confidence_score(candidate, policy)
        category = classify_category(candidate.vertical, candidate.title, candidate.snippet)
        approved.append(
            ApprovedTopic(
                id=candidate.id,
                vertical=candidate.vertical,
                title=candidate.title,
                source_urls=candidate.source_urls,
                discovered_at=candidate.discovered_at,
                confidence_score=conf,
                policy_score=policy.score,
                dedupe_hash=d_hash,
                category=category,
                policy_flags=policy.flags,
                snippet=candidate.snippet,
            )
        )
        history_titles.append(candidate.title)
        history_hashes.add(d_hash)

        if len(approved) >= max_count:
            break

    stats = ApprovalStats(
        candidate_count=len(candidate_list),
        duplicate_count=duplicate_count,
        policy_flag_count=policy_flag_count,
        blocked_count=blocked_count,
    )
    return approved, stats
