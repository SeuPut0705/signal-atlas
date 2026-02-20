from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from signal_atlas.content import build_generated_brief
from signal_atlas.models import ApprovedTopic, SourceMeta
from signal_atlas.publish import StaticSitePublisher


class PublishBasePathUnitTests(unittest.TestCase):
    def test_project_pages_base_path_links_are_prefixed(self) -> None:
        topic = ApprovedTopic(
            id="a1",
            vertical="ai_tech",
            category="ai",
            title="Signal Atlas test headline",
            source_urls=["https://example.com/a"],
            discovered_at="2026-02-19T00:00:00+09:00",
            confidence_score=0.9,
            policy_score=0.95,
            dedupe_hash="abc123",
            policy_flags=[],
            snippet="Test snippet",
            source_meta=[
                SourceMeta(
                    url="https://example.com/a",
                    title="External source",
                    description="External source description",
                    image="https://example.com/test-image.jpg",
                    site_name="Example",
                )
            ],
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
            self.assertIn('href="/signal-atlas/category/ai/index.html"', index_html)
            self.assertIn('href="/signal-atlas/category/ai/signal-atlas-test-headline.html"', index_html)
            self.assertIn('class="featured-media featured-media-text"', index_html)
            self.assertIn('class="cover-chip">AI</span>', index_html)
            self.assertNotIn('/signal-atlas/assets/thumbs/signal-atlas-test-headline.svg', index_html)
            self.assertIn('<script type="application/ld+json">{"@context":"https://schema.org"', index_html)
            self.assertNotIn("&quot;@context&quot;", index_html)

            thumb_svg = (site_dir / "assets" / "thumbs" / "signal-atlas-test-headline.svg").read_text(encoding="utf-8")
            self.assertIn("Signal Atlas test headline", thumb_svg)
            self.assertIn(">AI<", thumb_svg)
            self.assertIn("meaningful shift in AI", thumb_svg)

            article_html = (site_dir / "category" / "ai" / "signal-atlas-test-headline.html").read_text(encoding="utf-8")
            self.assertIn("<code>https://example.com/a</code>", article_html)
            self.assertNotIn('href="https://example.com/a"', article_html)
            self.assertNotIn('src="https://example.com/test-image.jpg"', article_html)
            self.assertIn(
                'property="og:image" content="https://foo.github.io/signal-atlas/assets/thumbs/signal-atlas-test-headline.svg"',
                article_html,
            )


if __name__ == "__main__":
    unittest.main()
