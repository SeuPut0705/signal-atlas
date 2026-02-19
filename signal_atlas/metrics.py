"""Metrics calculations and rollout signal helpers."""

from __future__ import annotations

from .constants import VERTICAL_AI_TECH, VERTICAL_FINANCE, VERTICAL_LIFESTYLE_POP
from .models import OpsMetrics

_VERTICAL_RPM_BASE = {
    VERTICAL_AI_TECH: 12.0,
    VERTICAL_FINANCE: 18.0,
    VERTICAL_LIFESTYLE_POP: 7.0,
}


def estimate_indexed_rate(candidate_count: int, publish_count: int, duplicate_rate: float, policy_flag_rate: float) -> float:
    """Heuristic indexability estimate when Search Console data is unavailable."""
    if candidate_count <= 0:
        return 0.0
    base = 0.26 + (publish_count * 0.007)
    penalty = (duplicate_rate * 0.55) + (policy_flag_rate * 0.45)
    score = base - penalty
    return round(max(0.0, min(0.95, score)), 4)


def estimate_rpm(vertical_publish_counts: dict[str, int], duplicate_rate: float, policy_flag_rate: float) -> float:
    """Estimate blended RPM from vertical mix and quality penalties."""
    total = sum(vertical_publish_counts.values())
    if total <= 0:
        return 0.0

    weighted = 0.0
    for vertical, count in vertical_publish_counts.items():
        share = count / total
        weighted += _VERTICAL_RPM_BASE.get(vertical, 8.0) * share

    quality = 1.0 - min(0.5, (duplicate_rate * 1.6) + (policy_flag_rate * 2.2))
    return round(max(0.0, weighted * quality), 3)


def build_ops_metrics(
    *,
    timestamp: str,
    candidate_count: int,
    duplicate_count: int,
    policy_flag_count: int,
    publish_count: int,
    vertical_publish_counts: dict[str, int],
) -> OpsMetrics:
    denominator = max(1, candidate_count)
    duplicate_rate = duplicate_count / denominator
    policy_flag_rate = policy_flag_count / denominator
    indexed_rate = estimate_indexed_rate(
        candidate_count=candidate_count,
        publish_count=publish_count,
        duplicate_rate=duplicate_rate,
        policy_flag_rate=policy_flag_rate,
    )
    rpm_estimate = estimate_rpm(
        vertical_publish_counts=vertical_publish_counts,
        duplicate_rate=duplicate_rate,
        policy_flag_rate=policy_flag_rate,
    )

    return OpsMetrics(
        timestamp=timestamp,
        indexed_rate=indexed_rate,
        duplicate_rate=round(duplicate_rate, 4),
        policy_flag_rate=round(policy_flag_rate, 4),
        rpm_estimate=rpm_estimate,
        publish_count=publish_count,
        candidate_count=candidate_count,
    )
