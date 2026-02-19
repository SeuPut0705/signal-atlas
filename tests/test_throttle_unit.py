from __future__ import annotations

import unittest

from signal_atlas.state import maybe_scale_publish_limit


class ThrottleUnitTests(unittest.TestCase):
    def test_scale_promotes_from_12_to_18_after_7_day_streak(self) -> None:
        state = {
            "publish_limit": 12,
            "daily_history": [
                {
                    "date": f"2026-02-{day:02d}",
                    "duplicate_rate": 0.03,
                    "policy_flag_rate": 0.005,
                    "indexed_rate": 0.41,
                    "rpm_estimate": 10.0,
                    "publish_count": 12,
                }
                for day in range(1, 8)
            ],
        }

        scaled_to = maybe_scale_publish_limit(state)
        self.assertEqual(scaled_to, 18)
        self.assertEqual(state["publish_limit"], 18)

    def test_scale_does_not_promote_when_one_day_fails(self) -> None:
        history = []
        for day in range(1, 8):
            history.append(
                {
                    "date": f"2026-02-{day:02d}",
                    "duplicate_rate": 0.03,
                    "policy_flag_rate": 0.005,
                    "indexed_rate": 0.41,
                    "rpm_estimate": 10.0,
                    "publish_count": 12,
                }
            )
        history[-1]["indexed_rate"] = 0.2

        state = {"publish_limit": 12, "daily_history": history}
        scaled_to = maybe_scale_publish_limit(state)
        self.assertIsNone(scaled_to)
        self.assertEqual(state["publish_limit"], 12)


if __name__ == "__main__":
    unittest.main()
