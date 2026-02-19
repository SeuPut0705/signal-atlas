from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from signal_atlas.content import build_generated_brief
from signal_atlas.models import ApprovedTopic
from signal_atlas.publish import StaticSitePublisher


class PublishBasePathUnitTests(unittest.TestCase):
    def test_project_pages_base_path_links_are_prefixed(self) -> None:
        topic = ApprovedTopic(
            id="a1",
            vertical="ai_tech",
            subcategory="ai-models",
            title="Signal Atlas test headline",
            source_urls=["https://example.com/a"],
            discovered_at="2026-02-19T00:00:00+09:00",
            confidence_score=0.9,
            policy_score=0.95,
            dedupe_hash="abc123",
            policy_flags=[],
            snippet="Test snippet",
        )
        generated = build_generated_brief(topic)

        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            publisher = StaticSitePublisher(
                site_dir=str(site_dir),
                site_url="https://foo.github.io/signal-atlas",
            )
            publisher.publish([generated], existing_rows=[], now_iso="2026-02-19T12:00:00+09:00")

            index_html = (site_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/signal-atlas/assets/site.css"', index_html)
            self.assertIn('href="/signal-atlas/ai_tech/index.html"', index_html)
            self.assertIn('href="/signal-atlas/ai_tech/ai-models/signal-atlas-test-headline.html"', index_html)


if __name__ == "__main__":
    unittest.main()
