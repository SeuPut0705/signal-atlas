from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RenderFromStateIntegrationTests(unittest.TestCase):
    def test_render_from_state_generates_story_topic_and_redirects(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            state_dir = work / "state"
            site_dir = work / "site"
            state_dir.mkdir(parents=True, exist_ok=True)
            state_file = state_dir / "pipeline_state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "timezone": "Asia/Seoul",
                        "created_at": "2026-02-20T00:00:00+09:00",
                        "updated_at": "2026-02-20T00:00:00+09:00",
                        "publish_limit": 12,
                        "disabled_verticals": [],
                        "vertical_deploy_failures": {"ai_tech": 0, "finance": 0, "lifestyle_pop": 0},
                        "published": [
                            {
                                "slug": "legacy-render",
                                "vertical": "ai_tech",
                                "title": "Legacy Render",
                                "published_at": "2026-02-20T00:00:00+09:00",
                                "word_count": 930,
                                "source_urls": ["https://example.com/a"],
                                "ad_slots": ["top-banner"],
                                "dedupe_hash": "legacy-render",
                                "path": "/category/ai/legacy-render.html",
                                "category": "ai",
                                "meta_description": "Legacy render description",
                            }
                        ],
                        "daily_history": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(repo_root / "render_site_from_state.py"),
                "--state-file",
                str(state_file),
                "--site-dir",
                str(site_dir),
                "--site-url",
                "https://foo.github.io/signal-atlas",
                "--url-schema",
                "v2",
            ]
            subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)

            self.assertTrue((site_dir / "stories" / "ai" / "legacy-render.html").exists())
            self.assertTrue((site_dir / "topics" / "ai" / "index.html").exists())
            legacy_redirect = (site_dir / "category" / "ai" / "legacy-render.html").read_text(encoding="utf-8")
            self.assertIn("refresh", legacy_redirect)


if __name__ == "__main__":
    unittest.main()
