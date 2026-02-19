"""Static publishing layer with sitemap, RSS, and ad slot injection."""

from __future__ import annotations

import html
import os
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .constants import ADSENSE_SLOTS, ALL_VERTICALS, PROJECT_TAGLINE, PROJECT_TITLE, VERTICAL_LABELS
from .models import GeneratedBrief, PublishedBrief
from .utils import ensure_dir


class StaticSitePublisher:
    def __init__(
        self,
        site_dir: str,
        site_url: str | None = None,
        adsense_client: str | None = None,
    ):
        self.site_dir = Path(site_dir)
        # Keep the legacy env var as a fallback for zero-downtime rename migration.
        self.site_url = (
            site_url
            or os.getenv("SIGNAL_ATLAS_SITE_URL")
            or os.getenv("AUTOTREND_SITE_URL")
            or "https://signal-atlas.example.com"
        ).rstrip("/")
        self.adsense_client = adsense_client or os.getenv("ADSENSE_CLIENT_ID") or "ca-pub-REPLACE_ME"
        parsed = urllib.parse.urlparse(self.site_url)
        path = (parsed.path or "").rstrip("/")
        self.base_path = "" if path in {"", "/"} else path

    def publish(
        self,
        generated_briefs: list[GeneratedBrief],
        existing_rows: Iterable[dict],
        now_iso: str,
    ) -> list[PublishedBrief]:
        existing_posts = self._load_existing_rows(existing_rows)
        new_posts: list[PublishedBrief] = []

        staging = self.site_dir.parent / f"{self.site_dir.name}.staging"
        backup = self.site_dir.parent / f"{self.site_dir.name}.backup"

        if staging.exists():
            shutil.rmtree(staging)

        if self.site_dir.exists():
            shutil.copytree(self.site_dir, staging)
        else:
            ensure_dir(staging)

        self._write_shared_assets(staging)

        for brief in generated_briefs:
            path = f"/{brief.topic.vertical}/{brief.slug}.html"
            published = PublishedBrief(
                slug=brief.slug,
                vertical=brief.topic.vertical,
                title=brief.topic.title,
                published_at=now_iso,
                word_count=brief.word_count,
                source_urls=brief.topic.source_urls,
                ad_slots=list(ADSENSE_SLOTS),
                dedupe_hash=brief.topic.dedupe_hash,
                path=path,
            )
            new_posts.append(published)

        all_posts = self._merge_posts(existing_posts, new_posts)
        all_posts.sort(key=lambda p: p.published_at, reverse=True)

        # Render post pages for new content.
        for post, brief in zip(new_posts, generated_briefs):
            internal_links = [p for p in all_posts if p.vertical == post.vertical and p.path != post.path][:5]
            html_body = self._render_post_html(brief, post, internal_links)
            out_path = staging / post.vertical / f"{post.slug}.html"
            ensure_dir(out_path.parent)
            out_path.write_text(html_body, encoding="utf-8")

        # Render aggregate pages.
        (staging / "index.html").write_text(self._render_home_html(all_posts), encoding="utf-8")
        for vertical in ALL_VERTICALS:
            vertical_posts = [p for p in all_posts if p.vertical == vertical]
            out_path = staging / vertical / "index.html"
            ensure_dir(out_path.parent)
            out_path.write_text(self._render_vertical_html(vertical, vertical_posts), encoding="utf-8")

        (staging / "sitemap.xml").write_text(self._render_sitemap(all_posts), encoding="utf-8")
        (staging / "rss.xml").write_text(self._render_rss(all_posts), encoding="utf-8")

        # Atomic-ish swap with restore path.
        if backup.exists():
            shutil.rmtree(backup)

        try:
            if self.site_dir.exists():
                self.site_dir.replace(backup)
            staging.replace(self.site_dir)
            if backup.exists():
                shutil.rmtree(backup)
        except Exception:
            if self.site_dir.exists() and self.site_dir != staging:
                shutil.rmtree(self.site_dir, ignore_errors=True)
            if backup.exists():
                backup.replace(self.site_dir)
            raise

        return new_posts

    def _load_existing_rows(self, rows: Iterable[dict]) -> list[PublishedBrief]:
        out: list[PublishedBrief] = []
        for row in rows:
            try:
                out.append(
                    PublishedBrief(
                        slug=str(row["slug"]),
                        vertical=str(row["vertical"]),
                        title=str(row["title"]),
                        published_at=str(row["published_at"]),
                        word_count=int(row.get("word_count") or 0),
                        source_urls=list(row.get("source_urls") or []),
                        ad_slots=list(row.get("ad_slots") or []),
                        dedupe_hash=str(row.get("dedupe_hash") or ""),
                        path=str(row["path"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def _merge_posts(self, existing: list[PublishedBrief], new: list[PublishedBrief]) -> list[PublishedBrief]:
        merged: dict[str, PublishedBrief] = {row.path: row for row in existing}
        for row in new:
            merged[row.path] = row
        return list(merged.values())

    def _write_shared_assets(self, root: Path) -> None:
        css_dir = root / "assets"
        ensure_dir(css_dir)
        (css_dir / "site.css").write_text(
            """
:root { --bg: #f7f8fb; --text: #1f2937; --muted: #6b7280; --card: #ffffff; --line: #d6dbe5; --accent: #0f766e; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Georgia, 'Times New Roman', serif; background: var(--bg); color: var(--text); }
main { max-width: 900px; margin: 0 auto; padding: 2rem 1rem 4rem; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
header.hero { margin-bottom: 1.5rem; }
header.hero h1 { margin: 0; font-size: 2rem; }
header.hero p { color: var(--muted); }
article, .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 1rem; }
.ad-slot { margin: 1rem 0; border: 1px dashed var(--line); border-radius: 10px; padding: 0.75rem; color: var(--muted); font-size: 0.9rem; text-align: center; }
ul.posts { list-style: none; padding: 0; margin: 0; }
ul.posts li { padding: 0.75rem 0; border-bottom: 1px solid var(--line); }
ul.posts li:last-child { border-bottom: none; }
small.meta { color: var(--muted); }
nav.verticals { display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 1rem 0 1.5rem; }
nav.verticals a { background: #e9f7f5; border: 1px solid #b8ece6; border-radius: 999px; padding: 0.35rem 0.75rem; font-size: 0.9rem; }
            """.strip()
            + "\n",
            encoding="utf-8",
        )

    def _html_page(self, title: str, body: str) -> str:
        esc_title = html.escape(title)
        return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{esc_title}</title>
  <meta name=\"description\" content=\"{html.escape(PROJECT_TAGLINE)}\" />
  <link rel=\"stylesheet\" href=\"{self._href('/assets/site.css')}\" />
  <script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={html.escape(self.adsense_client)}\" crossorigin=\"anonymous\"></script>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>
"""

    def _href(self, path: str) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.base_path}{normalized}" if self.base_path else normalized

    def _ad_slot(self, slot: str) -> str:
        return f"<div class=\"ad-slot\" data-slot=\"{html.escape(slot)}\">AdSense Slot: {html.escape(slot)}</div>"

    def _render_post_html(
        self,
        brief: GeneratedBrief,
        published: PublishedBrief,
        internal_links: list[PublishedBrief],
    ) -> str:
        payload = brief.payload
        src_items = "".join([f"<li><a href=\"{html.escape(u)}\" target=\"_blank\" rel=\"noopener\">{html.escape(u)}</a></li>" for u in payload["source_urls"]])
        kp_items = "".join([f"<li>{html.escape(line)}</li>" for line in payload["key_points"]])
        faq_items = "".join([f"<li><strong>{html.escape(item['q'])}</strong> {html.escape(item['a'])}</li>" for item in payload["faq"]])
        related = "".join([f"<li><a href=\"{html.escape(self._href(p.path))}\">{html.escape(p.title)}</a></li>" for p in internal_links])

        disclaimer = ""
        if payload.get("disclaimer"):
            disclaimer = f"<p><em>{html.escape(payload['disclaimer'])}</em></p>"

        body = f"""
<header class=\"hero\">
  <h1>{html.escape(payload['title'])}</h1>
  <p>{html.escape(VERTICAL_LABELS.get(brief.topic.vertical, brief.topic.vertical))} · <small class=\"meta\">{html.escape(published.published_at)}</small></p>
</header>
{self._ad_slot('top-banner')}
<article>
  {disclaimer}
  <h2>TL;DR</h2>
  <p>{html.escape(payload['summary'])}</p>
  <h2>Key Points</h2>
  <ul>{kp_items}</ul>
  {self._ad_slot('inline-1')}
  <h2>Why It Matters</h2>
  <p>This development changes distribution, monetization, and competitive timing across this vertical.</p>
  <h2>Sources</h2>
  <ul>{src_items}</ul>
  <h2>FAQ</h2>
  <ul>{faq_items}</ul>
  {self._ad_slot('inline-2')}
</article>
<article>
  <h3>Related Briefs</h3>
  <ul>{related or '<li>No related briefs yet.</li>'}</ul>
</article>
{self._ad_slot('footer')}
"""
        return self._html_page(payload["title"], body)

    def _render_home_html(self, posts: list[PublishedBrief]) -> str:
        items = "".join(
            [
                f"<li><a href=\"{html.escape(self._href(p.path))}\">{html.escape(p.title)}</a><br /><small class=\"meta\">{html.escape(VERTICAL_LABELS.get(p.vertical, p.vertical))} · {html.escape(p.published_at)}</small></li>"
                for p in posts[:60]
            ]
        )

        nav = "".join([f"<a href=\"{html.escape(self._href(f'/{v}/index.html'))}\">{html.escape(VERTICAL_LABELS[v])}</a>" for v in ALL_VERTICALS])
        body = f"""
<header class=\"hero\">
  <h1>{html.escape(PROJECT_TITLE)}</h1>
  <p>{html.escape(PROJECT_TAGLINE)}</p>
</header>
<nav class=\"verticals\">{nav}</nav>
{self._ad_slot('top-banner')}
<div class=\"card\">
  <h2>Latest Briefings</h2>
  <ul class=\"posts\">{items or '<li>No briefs yet.</li>'}</ul>
</div>
"""
        return self._html_page(PROJECT_TITLE, body)

    def _render_vertical_html(self, vertical: str, posts: list[PublishedBrief]) -> str:
        items = "".join(
            [
                f"<li><a href=\"{html.escape(self._href(p.path))}\">{html.escape(p.title)}</a><br /><small class=\"meta\">{html.escape(p.published_at)}</small></li>"
                for p in posts[:80]
            ]
        )
        label = VERTICAL_LABELS.get(vertical, vertical)
        body = f"""
<header class=\"hero\">
  <h1>{html.escape(label)}</h1>
  <p><a href=\"{html.escape(self._href('/index.html'))}\">Back to home</a></p>
</header>
{self._ad_slot('top-banner')}
<div class=\"card\">
  <h2>Recent stories</h2>
  <ul class=\"posts\">{items or '<li>No stories yet.</li>'}</ul>
</div>
"""
        return self._html_page(f"{label} · {PROJECT_TITLE}", body)

    def _render_sitemap(self, posts: list[PublishedBrief]) -> str:
        urls = [f"{self.site_url}/index.html", *[f"{self.site_url}/{v}/index.html" for v in ALL_VERTICALS]]
        urls.extend([f"{self.site_url}{post.path}" for post in posts])

        body = "\n".join([f"  <url><loc>{html.escape(url)}</loc></url>" for url in urls])
        return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
{body}
</urlset>
"""

    def _render_rss(self, posts: list[PublishedBrief]) -> str:
        items: list[str] = []
        for post in posts[:40]:
            pub = post.published_at
            try:
                dt = datetime.fromisoformat(pub)
                pub = dt.strftime("%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                pass

            items.append(
                "\n".join(
                    [
                        "  <item>",
                        f"    <title>{html.escape(post.title)}</title>",
                        f"    <link>{html.escape(self.site_url + post.path)}</link>",
                        f"    <guid>{html.escape(self.site_url + post.path)}</guid>",
                        f"    <pubDate>{html.escape(pub)}</pubDate>",
                        "  </item>",
                    ]
                )
            )

        items_blob = "\n".join(items)
        return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\">
<channel>
  <title>{html.escape(PROJECT_TITLE)}</title>
  <link>{html.escape(self.site_url)}</link>
  <description>{html.escape(PROJECT_TAGLINE)}</description>
{items_blob}
</channel>
</rss>
"""
