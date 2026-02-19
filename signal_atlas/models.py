"""Data contracts for Signal Atlas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TopicCandidate:
    id: str
    vertical: str
    title: str
    source_urls: list[str]
    discovered_at: str
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApprovedTopic:
    id: str
    vertical: str
    title: str
    source_urls: list[str]
    discovered_at: str
    confidence_score: float
    policy_score: float
    dedupe_hash: str
    policy_flags: list[str] = field(default_factory=list)
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PublishedBrief:
    slug: str
    vertical: str
    title: str
    published_at: str
    word_count: int
    source_urls: list[str]
    ad_slots: list[str]
    dedupe_hash: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OpsMetrics:
    timestamp: str
    indexed_rate: float
    duplicate_rate: float
    policy_flag_rate: float
    rpm_estimate: float
    publish_count: int
    candidate_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyResult:
    score: float
    flags: list[str]
    blocked: bool


@dataclass
class GeneratedBrief:
    topic: ApprovedTopic
    slug: str
    markdown: str
    payload: dict[str, Any]
    word_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "topic": self.topic.to_dict(),
            "payload": self.payload,
            "word_count": self.word_count,
        }
