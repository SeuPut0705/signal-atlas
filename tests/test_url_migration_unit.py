from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from signal_atlas.content import build_generated_brief
from signal_atlas.models import ApprovedTopic, SourceMeta
from signal_atlas.publish import StaticSitePublisher, build_category_path, build_story_path


class UrlMigrationUnitTests(unittest.TestCase):
    def test_v2_path_builders(self) -> None:
        self.assertEqual(build_category_path("ai", "v2"), "/topics/ai/index.html")
        self.assertEqual(build_story_path("ai", "hello-world", "v2"), "/stories/ai/hello-world.html")

    def test_slug_collision_adds_suffix(self) -> None:
        topic1 = ApprovedTopic(
            id="x1",
            vertical="ai_tech",
            category="ai",
            title="Same Headline",
            source_urls=["https://example.com/1"],
            discovered_at="2026-02-20T00:00:00+09:00",
            confidence_score=0.9,
            policy_score=0.95,
            dedupe_hash="d1",
            source_meta=[SourceMeta(url="https://example.com/1")],
        )
        topic2 = ApprovedTopic(
            id="x2",
            vertical="ai_tech",
            category="ai",
            title="Same Headline",
            source_urls=["https://example.com/2"],
            discovered_at="2026-02-20T00:00:00+09:00",
            confidence_score=0.9,
            policy_score=0.95,
            dedupe_hash="d2",
            source_meta=[SourceMeta(url="https://example.com/2")],
        )
        brief1 = build_generated_brief(topic1)
        brief2 = build_generated_brief(topic2)

        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            publisher = StaticSitePublisher(site_dir=str(site_dir), site_url="https://foo.github.io/signal-atlas")
            published = publisher.publish([brief1, brief2], existing_rows=[], now_iso="2026-02-20T10:00:00+09:00")

            slugs = sorted([one.slug for one in published])
            self.assertEqual(slugs, ["same-headline", "same-headline-2"])
            self.assertTrue((site_dir / "stories" / "ai" / "same-headline.html").exists())
            self.assertTrue((site_dir / "stories" / "ai" / "same-headline-2.html").exists())

    def test_legacy_category_path_is_redirected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            publisher = StaticSitePublisher(site_dir=str(site_dir), site_url="https://foo.github.io/signal-atlas")
            publisher.publish(
                generated_briefs=[],
                existing_rows=[
                    {
                        "slug": "legacy",
                        "vertical": "ai_tech",
                        "title": "Legacy",
                        "published_at": "2026-02-20T00:00:00+09:00",
                        "word_count": 900,
                        "source_urls": ["https://example.com/a"],
                        "ad_slots": ["top-banner"],
                        "dedupe_hash": "legacy",
                        "path": "/category/ai/legacy.html",
                        "category": "ai",
                        "meta_description": "Legacy description",
                    }
                ],
                now_iso="2026-02-20T10:00:00+09:00",
            )

            story = site_dir / "stories" / "ai" / "legacy.html"
            redirect = site_dir / "category" / "ai" / "legacy.html"
            self.assertTrue(story.exists())
            self.assertTrue(redirect.exists())
            self.assertIn("refresh", redirect.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

