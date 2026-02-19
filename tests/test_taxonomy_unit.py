from __future__ import annotations

import unittest

from signal_atlas.taxonomy import classify_subcategory


class TaxonomyUnitTests(unittest.TestCase):
    def test_ai_models_subcategory(self) -> None:
        sub = classify_subcategory(
            "ai_tech",
            "Open source reasoning model launch shakes enterprise roadmap",
            "Teams compare multimodal model benchmarks for inference cost.",
        )
        self.assertEqual(sub, "ai-models")

    def test_fintech_subcategory(self) -> None:
        sub = classify_subcategory(
            "finance",
            "Payment wallet competition intensifies across neobank apps",
            "Fintech players race to lower transaction fees.",
        )
        self.assertEqual(sub, "fintech-payments")

    def test_general_fallback(self) -> None:
        sub = classify_subcategory(
            "lifestyle_pop",
            "Weekend city guide highlights new cafe districts",
            "A broad recap without platform-specific keywords.",
        )
        self.assertEqual(sub, "general")


if __name__ == "__main__":
    unittest.main()
