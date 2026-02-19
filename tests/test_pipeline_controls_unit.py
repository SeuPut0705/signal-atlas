from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from signal_atlas.ingest import IngestMeta
from signal_atlas.models import GeneratedBrief, TopicCandidate
from signal_atlas.pipeline import Pipeline


class _MiniIngestor:
    def collect(self, vertical: str, now: datetime, max_candidates: int = 60):
        title_bank = [
            "Semiconductor capex rebound reshapes edge compute supply chain",
            "Telehealth reimbursement policy update shifts provider margins",
            "Consumer payment rails upgrade changes cross-border settlement pace",
        ]
        items = []
        for idx in range(1, 4):
            items.append(
                TopicCandidate(
                    id=f"{vertical}-{idx}",
                    vertical=vertical,
                    title=f"{title_bank[idx - 1]} {vertical}",
                    source_urls=[f"https://example.com/{vertical}/{idx}"],
                    discovered_at=now.isoformat(timespec="seconds"),
                    snippet="Deterministic snippet for budget-control tests.",
                )
            )
        return items, IngestMeta(source_failures=0, used_fallback=False)


class PipelineControlsUnitTests(unittest.TestCase):
    def test_budget_downgrade_and_template_fallback(self) -> None:
        seen_quality: list[str] = []

        def fake_build_generated_brief(topic, **kwargs):
            engine = kwargs.get("generation_engine", "gemini")
            quality = kwargs.get("quality_tier", "premium")
            seen_quality.append(quality)
            cost = 0.0
            if engine == "gemini":
                cost = 140.0 if quality == "premium" else 80.0
            payload = {
                "generation_engine": engine,
                "generation_cost_krw": cost,
                "source_urls": topic.source_urls,
            }
            return GeneratedBrief(
                topic=topic,
                slug=f"{topic.id}-brief",
                markdown="# Brief",
                payload=payload,
                word_count=900,
            )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pipe = Pipeline(
                state_file=str(base / "state" / "pipeline_state.json"),
                metrics_file=str(base / "state" / "ops_metrics.jsonl"),
                artifacts_dir=str(base / "artifacts"),
                site_dir=str(base / "site"),
                ingestor=_MiniIngestor(),
            )

            with patch.dict("os.environ", {"MONTHLY_BUDGET_KRW": "300"}, clear=False):
                with patch("signal_atlas.pipeline.build_generated_brief", side_effect=fake_build_generated_brief):
                    out = pipe.run(
                        vertical="ai_tech",
                        max_publish=3,
                        mode="dry-run",
                        generation_engine="gemini",
                        quality_tier="premium",
                    )

            self.assertIn("balanced", seen_quality)
            self.assertGreaterEqual(out["generation_usage"].get("template", 0), 1)
            self.assertGreater(out["budget"]["spent_krw"], 0)
            self.assertLessEqual(out["budget"]["spent_krw"], 300)


if __name__ == "__main__":
    unittest.main()
