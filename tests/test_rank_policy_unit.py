from __future__ import annotations

import unittest

from signal_atlas.models import TopicCandidate
from signal_atlas.policy import evaluate_policy
from signal_atlas.rank import approve_topics
from signal_atlas.utils import dedupe_hash


class RankPolicyUnitTests(unittest.TestCase):
    def test_duplicate_detection_catches_near_title(self) -> None:
        history = [
            {
                "title": "AI copilots are reshaping developer workflow this quarter",
                "dedupe_hash": dedupe_hash("AI copilots are reshaping developer workflow this quarter"),
            }
        ]
        candidates = [
            TopicCandidate(
                id="c1",
                vertical="ai_tech",
                title="AI copilots reshaping developer workflows this quarter",
                source_urls=["https://example.com/a"],
                discovered_at="2026-02-19T00:00:00+09:00",
                snippet="Developers are adopting copilots faster than expected.",
            )
        ]

        approved, stats = approve_topics(candidates, history_rows=history, max_count=3)
        self.assertEqual(len(approved), 0)
        self.assertEqual(stats.duplicate_count, 1)

    def test_finance_policy_blocks_investment_advice(self) -> None:
        topic = TopicCandidate(
            id="c2",
            vertical="finance",
            title="Buy now before guaranteed return window closes",
            source_urls=["https://example.com/f"],
            discovered_at="2026-02-19T00:00:00+09:00",
            snippet="Invest now for risk free gains.",
        )
        result = evaluate_policy(topic)
        self.assertTrue(result.blocked)
        self.assertIn("finance_investment_advice", result.flags)

    def test_missing_source_is_blocked(self) -> None:
        topic = TopicCandidate(
            id="c3",
            vertical="ai_tech",
            title="Enterprise AI benchmark update",
            source_urls=[],
            discovered_at="2026-02-19T00:00:00+09:00",
            snippet="Benchmarks changed after latest release.",
        )
        result = evaluate_policy(topic)
        self.assertTrue(result.blocked)
        self.assertIn("missing_source", result.flags)


if __name__ == "__main__":
    unittest.main()
