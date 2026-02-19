from __future__ import annotations

import unittest

from signal_atlas.taxonomy import classify_category


class TaxonomyUnitTests(unittest.TestCase):
    def test_ai_category(self) -> None:
        category = classify_category(
            "ai_tech",
            "Open source reasoning model launch shakes enterprise roadmap",
            "Teams compare multimodal model benchmarks for inference cost.",
        )
        self.assertEqual(category, "ai")

    def test_finance_category(self) -> None:
        category = classify_category(
            "finance",
            "Payment wallet competition intensifies across neobank apps",
            "Fintech players race to lower transaction fees.",
        )
        self.assertEqual(category, "finance")

    def test_tech_category(self) -> None:
        category = classify_category(
            "lifestyle_pop",
            "Major streaming platform rolls out developer API toolkit",
            "Cloud app teams adopt new software platform integration.",
        )
        self.assertEqual(category, "tech")

    def test_general_fallback(self) -> None:
        category = classify_category(
            "lifestyle_pop",
            "Weekend city guide highlights new cafe districts",
            "A broad recap without platform-specific keywords.",
        )
        self.assertEqual(category, "general")


if __name__ == "__main__":
    unittest.main()
