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
            self.assertIn('href="/signal-atlas/topics/ai/index.html"', index_html)
            self.assertIn('href="/signal-atlas/stories/ai/signal-atlas-test-headline.html"', index_html)
            self.assertIn('class="skip-link" href="#main-content"', index_html)
            self.assertIn('aria-current="page">Home</a>', index_html)
            self.assertIn('>Healthcare</a>', index_html)
            self.assertIn('>Startup</a>', index_html)
            self.assertIn('>General</a>', index_html)
            self.assertIn('class="featured-media featured-media-text"', index_html)
            self.assertIn('class="cover-chip">AI</span>', index_html)
            self.assertNotIn('/signal-atlas/assets/thumbs/signal-atlas-test-headline.svg', index_html)
            self.assertIn('<script type="application/ld+json">{"@context":"https://schema.org"', index_html)
            self.assertNotIn("&quot;@context&quot;", index_html)

            thumb_svg = (site_dir / "assets" / "thumbs" / "signal-atlas-test-headline.svg").read_text(encoding="utf-8")
            self.assertIn("Signal Atlas test headline", thumb_svg)
            self.assertIn(">AI<", thumb_svg)
            self.assertIn("meaningful shift in AI", thumb_svg)

            article_html = (site_dir / "stories" / "ai" / "signal-atlas-test-headline.html").read_text(encoding="utf-8")
            self.assertIn('class="article-cover featured-media featured-media-text" data-category="ai"', article_html)
            self.assertNotIn('class="hero-image"', article_html)
            self.assertIn('aria-current="page">AI</a>', article_html)
            self.assertIn('property="og:site_name" content="Signal Atlas"', article_html)
            self.assertIn('type="application/rss+xml"', article_html)
            self.assertNotIn('data-slot="inline-3"', article_html)
            self.assertIn("<code>https://example.com/a</code>", article_html)
            self.assertNotIn('href="https://example.com/a"', article_html)
            self.assertNotIn('src="https://example.com/test-image.jpg"', article_html)
            self.assertIn(
                'property="og:image" content="https://foo.github.io/signal-atlas/assets/thumbs/signal-atlas-test-headline.svg"',
                article_html,
            )

            legacy_story_redirect = (
                site_dir / "category" / "ai" / "signal-atlas-test-headline.html"
            ).read_text(encoding="utf-8")
            self.assertIn('http-equiv="refresh"', legacy_story_redirect)
            self.assertIn('/signal-atlas/stories/ai/signal-atlas-test-headline.html', legacy_story_redirect)

            legacy_topic_redirect = (site_dir / "category" / "ai" / "index.html").read_text(encoding="utf-8")
            self.assertIn('http-equiv="refresh"', legacy_topic_redirect)
            self.assertIn('/signal-atlas/topics/ai/index.html', legacy_topic_redirect)

    def test_existing_post_hero_image_is_rewritten_to_text_cover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            old_post_path = site_dir / "category" / "ai" / "legacy-post.html"
            old_post_path.parent.mkdir(parents=True, exist_ok=True)
            old_post_path.write_text(
                "<html><body><article>"
                '<img class="hero-image" src="/assets/covers/ai.svg" alt="legacy" loading="eager" width="1200" height="675" />'
                "<p>Legacy body</p>"
                "</article></body></html>",
                encoding="utf-8",
            )

            publisher = StaticSitePublisher(
                site_dir=str(site_dir),
                site_url="https://foo.github.io/signal-atlas",
            )
            publisher.publish(
                generated_briefs=[],
                existing_rows=[
                    {
                        "slug": "legacy-post",
                        "vertical": "ai_tech",
                        "title": "Legacy Post",
                        "published_at": "2026-02-19T12:00:00+09:00",
                        "word_count": 900,
                        "source_urls": ["https://example.com/legacy"],
                        "ad_slots": ["top-banner"],
                        "dedupe_hash": "legacy-hash",
                        "path": "/category/ai/legacy-post.html",
                        "category": "ai",
                        "primary_image": "/assets/covers/ai.svg",
                        "seo_title": "Legacy Post",
                        "meta_description": "Legacy description",
                    }
                ],
                now_iso="2026-02-19T12:00:00+09:00",
            )

            rewritten = (site_dir / "stories" / "ai" / "legacy-post.html").read_text(encoding="utf-8")
            self.assertIn('class="article-cover featured-media featured-media-text" data-category="ai"', rewritten)
            self.assertNotIn('class="hero-image"', rewritten)
            legacy_redirect = old_post_path.read_text(encoding="utf-8")
            self.assertIn('http-equiv="refresh"', legacy_redirect)
            self.assertIn('/signal-atlas/stories/ai/legacy-post.html', legacy_redirect)

    def test_inline_3_slot_appears_for_long_article(self) -> None:
        topic = ApprovedTopic(
            id="a2",
            vertical="ai_tech",
            category="ai",
            title="Signal Atlas long-form headline",
            source_urls=["https://example.com/a"],
            discovered_at="2026-02-19T00:00:00+09:00",
            confidence_score=0.9,
            policy_score=0.95,
            dedupe_hash="abc124",
            policy_flags=[],
            snippet="Long test snippet",
            source_meta=[SourceMeta(url="https://example.com/a")],
        )
        generated = build_generated_brief(topic)
        generated.word_count = 1200
        generated.payload["word_count"] = 1200

        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            publisher = StaticSitePublisher(
                site_dir=str(site_dir),
                site_url="https://foo.github.io/signal-atlas",
            )
            publisher.publish([generated], existing_rows=[], now_iso="2026-02-19T12:00:00+09:00")
            article_html = (site_dir / "stories" / "ai" / "signal-atlas-long-form-headline.html").read_text(encoding="utf-8")
            self.assertIn('data-slot="inline-3"', article_html)


if __name__ == "__main__":
    unittest.main()
