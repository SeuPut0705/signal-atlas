from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from signal_atlas.ingest import IngestMeta, Ingestor
from signal_atlas.models import TopicCandidate
from signal_atlas.pipeline import Pipeline
from signal_atlas.publish import StaticSitePublisher
from signal_atlas.state import load_state


class _StaticIngestor:
    def __init__(self, title_prefix: str = "Signal"):
        self.title_prefix = title_prefix

    def collect(self, vertical: str, now: datetime, max_candidates: int = 60):
        title_bank = [
            "infrastructure spending rotation",
            "developer platform consolidation",
            "inference cost reset",
            "data governance automation",
            "creator distribution shift",
            "enterprise buying cycle",
        ]
        items = []
        for idx in range(1, min(max_candidates, 4) + 1):
            base_title = title_bank[idx - 1]
            items.append(
                TopicCandidate(
                    id=f"{vertical}-{idx}",
                    vertical=vertical,
                    title=f"{self.title_prefix} {base_title} {vertical}",
                    source_urls=[f"https://example.com/{vertical}/{idx}"],
                    discovered_at=now.isoformat(timespec="seconds"),
                    snippet="Deterministic test snippet for pipeline coverage.",
                )
            )
        return items, IngestMeta(source_failures=0, used_fallback=False)


class _FlakyPublisher:
    def __init__(self, site_dir: str, fail_times: int):
        self.fail_times = fail_times
        self.attempts = 0
        self.delegate = StaticSitePublisher(site_dir=site_dir)

    def publish(self, generated_briefs, existing_rows, now_iso):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise RuntimeError("simulated deploy failure")
        return self.delegate.publish(generated_briefs, existing_rows, now_iso)


class _AlwaysFailPublisher:
    def __init__(self):
        self.attempts = 0

    def publish(self, generated_briefs, existing_rows, now_iso):
        self.attempts += 1
        raise RuntimeError("always fail")


class PipelineIntegrationTests(unittest.TestCase):
    def test_source_failure_uses_fallback_in_dry_run(self) -> None:
        def always_fail_fetch(_query: str):
            raise TimeoutError("source down")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pipe = Pipeline(
                state_file=str(base / "state" / "pipeline_state.json"),
                metrics_file=str(base / "state" / "ops_metrics.jsonl"),
                artifacts_dir=str(base / "artifacts"),
                site_dir=str(base / "site"),
                ingestor=Ingestor(fetch_query=always_fail_fetch),
            )

            out = pipe.run(vertical="finance", max_publish=4, mode="dry-run")
            self.assertEqual(out["per_vertical"]["finance"]["used_fallback"], True)
            self.assertGreaterEqual(out["published"], 1)

    def test_production_publish_retries_then_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            publisher = _FlakyPublisher(site_dir=str(base / "site"), fail_times=2)
            pipe = Pipeline(
                state_file=str(base / "state" / "pipeline_state.json"),
                metrics_file=str(base / "state" / "ops_metrics.jsonl"),
                artifacts_dir=str(base / "artifacts"),
                site_dir=str(base / "site"),
                ingestor=_StaticIngestor("Retry Test"),
                publisher=publisher,
            )

            out = pipe.run(vertical="ai_tech", max_publish=2, mode="production")
            self.assertEqual(out["deploy_attempts"], 3)
            self.assertEqual(out["published"], 2)
            self.assertTrue((base / "site" / "index.html").exists())

    def test_vertical_is_disabled_after_3_failed_deploy_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pipe = Pipeline(
                state_file=str(base / "state" / "pipeline_state.json"),
                metrics_file=str(base / "state" / "ops_metrics.jsonl"),
                artifacts_dir=str(base / "artifacts"),
                site_dir=str(base / "site"),
                ingestor=_StaticIngestor("Fail Test"),
                publisher=_AlwaysFailPublisher(),
            )

            for _ in range(3):
                pipe.run(vertical="ai_tech", max_publish=1, mode="production")

            state = load_state(str(base / "state" / "pipeline_state.json"), now_iso=datetime.now().isoformat())
            self.assertIn("ai_tech", state["disabled_verticals"])


if __name__ == "__main__":
    unittest.main()
