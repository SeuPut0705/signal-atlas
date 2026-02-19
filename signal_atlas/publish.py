"""Static publishing layer with magazine UI, SEO, and ad slot injection."""

from __future__ import annotations

import html
import json
import os
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .constants import ADSENSE_SLOTS, ALL_CATEGORIES, ALL_VERTICALS, CATEGORY_LABELS, PROJECT_TAGLINE, PROJECT_TITLE
from .models import GeneratedBrief, PublishedBrief
from .utils import ensure_dir

_COVER_COLORS = {
    "ai": ("#0ea5e9", "#0369a1"),
    "tech": ("#22c55e", "#15803d"),
    "finance": ("#f59e0b", "#b45309"),
    "healthcare": ("#ef4444", "#b91c1c"),
    "stocks": ("#a855f7", "#7e22ce"),
    "startup": ("#14b8a6", "#0f766e"),
    "general": ("#64748b", "#334155"),
}


class StaticSitePublisher:
    def __init__(
        self,
        site_dir: str,
        site_url: str | None = None,
        adsense_client: str | None = None,
    ):
        self.site_dir = Path(site_dir)
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

        self._cleanup_legacy_pages(staging)
        self._write_shared_assets(staging)

        for brief in generated_briefs:
            path = f"/category/{brief.topic.category}/{brief.slug}.html"
            primary_image = str(brief.payload.get("hero_image_url") or f"/assets/covers/{brief.topic.category}.svg")
            published = PublishedBrief(
                slug=brief.slug,
                vertical=brief.topic.vertical,
                title=brief.topic.title,
                published_at=now_iso,
                word_count=brief.word_count,
                source_urls=list(brief.payload.get("source_urls") or brief.topic.source_urls),
                ad_slots=list(ADSENSE_SLOTS),
                dedupe_hash=brief.topic.dedupe_hash,
                path=path,
                category=brief.topic.category,
                primary_image=primary_image,
                seo_title=str(brief.payload.get("seo_title") or brief.topic.title),
                meta_description=str(brief.payload.get("meta_description") or PROJECT_TAGLINE),
            )
            new_posts.append(published)

        all_posts = self._merge_posts(existing_posts, new_posts)
        all_posts.sort(key=lambda p: str(p.published_at), reverse=True)

        # Render post pages for new content.
        for post, brief in zip(new_posts, generated_briefs):
            internal_links = [p for p in all_posts if p.category == post.category and p.path != post.path][:6]
            html_body = self._render_post_html(brief, post, internal_links)
            out_path = staging / "category" / post.category / f"{post.slug}.html"
            ensure_dir(out_path.parent)
            out_path.write_text(html_body, encoding="utf-8")

        # Render aggregate pages.
        (staging / "index.html").write_text(self._render_home_html(all_posts), encoding="utf-8")
        for category in ALL_CATEGORIES:
            category_posts = [p for p in all_posts if p.category == category]
            out_path = staging / "category" / category / "index.html"
            ensure_dir(out_path.parent)
            out_path.write_text(self._render_category_html(category, category_posts), encoding="utf-8")

        (staging / "robots.txt").write_text(self._render_robots(), encoding="utf-8")
        (staging / "sitemap.xml").write_text(self._render_sitemap(all_posts), encoding="utf-8")
        (staging / "rss.xml").write_text(self._render_rss(all_posts), encoding="utf-8")

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
                        vertical=str(row.get("vertical") or ""),
                        title=str(row["title"]),
                        published_at=str(row["published_at"]),
                        word_count=int(row.get("word_count") or 0),
                        source_urls=list(row.get("source_urls") or []),
                        ad_slots=list(row.get("ad_slots") or []),
                        dedupe_hash=str(row.get("dedupe_hash") or ""),
                        path=str(row["path"]),
                        category=str(row.get("category") or row.get("subcategory") or "general"),
                        primary_image=str(row.get("primary_image") or ""),
                        seo_title=str(row.get("seo_title") or row.get("title") or ""),
                        meta_description=str(row.get("meta_description") or PROJECT_TAGLINE),
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

    def _cleanup_legacy_pages(self, root: Path) -> None:
        for vertical in ALL_VERTICALS:
            old_dir = root / vertical
            if old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)

    def _write_shared_assets(self, root: Path) -> None:
        css_dir = root / "assets"
        covers_dir = css_dir / "covers"
        ensure_dir(covers_dir)

        (css_dir / "site.css").write_text(
            """
:root {
  --bg: #f3f5f9;
  --text: #111827;
  --muted: #6b7280;
  --line: #d9dfe8;
  --card: #ffffff;
  --accent: #0f172a;
  --accent-soft: #e2e8f0;
  --radius: 14px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
  background:
    radial-gradient(1100px 560px at -10% -25%, #dbeafe 0%, transparent 62%),
    radial-gradient(900px 450px at 110% -15%, #fde68a 0%, transparent 60%),
    var(--bg);
  color: var(--text);
}
main { max-width: 1160px; margin: 0 auto; padding: 1.2rem 1rem 3rem; }
a { color: #0b3ea6; text-decoration: none; }
a:hover { text-decoration: underline; }
a:focus-visible { outline: 2px solid #0b3ea6; outline-offset: 2px; border-radius: 6px; }
.header-kicker { text-transform: uppercase; letter-spacing: .08em; font-size: .75rem; color: var(--muted); font-weight: 700; }
header.hero { margin-bottom: 1.2rem; }
header.hero h1 {
  margin: .2rem 0 .35rem;
  font-family: 'Newsreader', Georgia, serif;
  font-size: clamp(2rem, 3.6vw, 3.3rem);
  line-height: 1.05;
  letter-spacing: -0.01em;
}
header.hero p { margin: 0; color: var(--muted); font-size: 1.05rem; }
nav.categories { display: flex; gap: .52rem; flex-wrap: wrap; margin: 1rem 0 1.4rem; }
nav.categories a {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: .38rem .78rem;
  font-size: .92rem;
  font-weight: 600;
  color: #1f2937;
}
.layout-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}
.featured {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.featured-media { position: relative; aspect-ratio: 16 / 9; background: #cbd5e1; }
.featured-media img { width: 100%; height: 100%; object-fit: cover; display: block; }
.featured-body { padding: 1rem 1.1rem 1.1rem; }
.featured h2 {
  font-family: 'Newsreader', Georgia, serif;
  font-size: clamp(1.36rem, 2.5vw, 2rem);
  margin: 0 0 .45rem;
  line-height: 1.15;
}
.featured p { margin: 0; color: #374151; }
.trending {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: .95rem 1rem;
}
.trending h3 {
  margin: .1rem 0 .8rem;
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1.25rem;
}
.trending ol { margin: 0; padding-left: 1.1rem; display: grid; gap: .75rem; }
.trending li { color: #374151; }
.story-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .95rem;
}
.story-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  min-height: 100%;
}
.story-media { aspect-ratio: 16 / 9; background: #e2e8f0; }
.story-media img { width: 100%; height: 100%; object-fit: cover; display: block; }
.story-body { padding: .84rem .9rem 1rem; }
.story-title {
  margin: 0 0 .32rem;
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1.15rem;
  line-height: 1.2;
}
.story-summary {
  margin: 0;
  color: #4b5563;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta-line { color: var(--muted); font-size: .87rem; margin-top: .45rem; }
.article {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1rem 1.2rem;
  margin-bottom: 1rem;
}
.article h2 {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1.45rem;
  margin-top: 1.4rem;
}
.article p { line-height: 1.7; margin: .82rem 0; }
.article ul { line-height: 1.6; }
.hero-image {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: calc(var(--radius) - 4px);
  border: 1px solid var(--line);
  object-fit: cover;
  margin: .8rem 0 1rem;
  background: #e2e8f0;
}
.section-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1rem;
}
.panel {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: .95rem 1rem;
}
.panel h3 {
  margin: .2rem 0 .6rem;
  font-family: 'Newsreader', Georgia, serif;
}
.ad-slot {
  margin: .9rem 0;
  border: 1px dashed #94a3b8;
  border-radius: 10px;
  padding: .72rem;
  color: #475569;
  font-size: .88rem;
  text-align: center;
  background: #f8fafc;
}
.footer-note { margin-top: 2rem; color: var(--muted); font-size: .9rem; }
@media (max-width: 959px) {
  .layout-grid, .section-grid { grid-template-columns: 1fr; }
  .story-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 639px) {
  main { padding: 1rem .75rem 2.2rem; }
  .story-grid { grid-template-columns: 1fr; }
  .article { padding: .86rem .9rem; }
  nav.categories { gap: .4rem; }
  nav.categories a { font-size: .85rem; padding: .34rem .62rem; }
}
            """.strip()
            + "\n",
            encoding="utf-8",
        )

        for category in ALL_CATEGORIES:
            c1, c2 = _COVER_COLORS.get(category, _COVER_COLORS["general"])
            label = CATEGORY_LABELS.get(category, category).upper()
            svg = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 675' role='img' aria-label='{html.escape(label)}'>
<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%' stop-color='{c1}'/><stop offset='100%' stop-color='{c2}'/></linearGradient></defs>
<rect width='1200' height='675' fill='url(#g)'/>
<circle cx='1040' cy='120' r='220' fill='rgba(255,255,255,.15)'/>
<circle cx='140' cy='560' r='240' fill='rgba(255,255,255,.12)'/>
<text x='72' y='570' fill='rgba(255,255,255,.95)' font-family='Georgia,serif' font-size='72' letter-spacing='2'>{html.escape(label)}</text>
</svg>"""
            (covers_dir / f"{category}.svg").write_text(svg, encoding="utf-8")

    def _href(self, path: str) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.base_path}{normalized}" if self.base_path else normalized

    def _public_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.site_url}{normalized}"

    def _ad_slot(self, slot: str) -> str:
        return f"<div class=\"ad-slot\" data-slot=\"{html.escape(slot)}\">AdSense Slot: {html.escape(slot)}</div>"

    def _seo_head(
        self,
        *,
        title: str,
        description: str,
        canonical_path: str,
        og_type: str = "website",
        og_image: str = "",
        json_ld_objects: list[dict] | None = None,
    ) -> str:
        canonical_url = self._public_url(canonical_path)
        image_url = self._public_url(og_image) if og_image else ""
        json_ld = ""
        for one in json_ld_objects or []:
            blob = json.dumps(one, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
            json_ld += "\n" + f"<script type=\"application/ld+json\">{blob}</script>"

        og_image_tag = f'<meta property="og:image" content="{html.escape(image_url)}" />' if image_url else ""
        tw_image_tag = f'<meta name="twitter:image" content="{html.escape(image_url)}" />' if image_url else ""

        return f"""
  <meta name=\"description\" content=\"{html.escape(description)}\" />
  <link rel=\"canonical\" href=\"{html.escape(canonical_url)}\" />
  <link rel=\"alternate\" hreflang=\"en\" href=\"{html.escape(canonical_url)}\" />
  <meta property=\"og:type\" content=\"{html.escape(og_type)}\" />
  <meta property=\"og:title\" content=\"{html.escape(title)}\" />
  <meta property=\"og:description\" content=\"{html.escape(description)}\" />
  <meta property=\"og:url\" content=\"{html.escape(canonical_url)}\" />
  {og_image_tag}
  <meta name=\"twitter:card\" content=\"summary_large_image\" />
  <meta name=\"twitter:title\" content=\"{html.escape(title)}\" />
  <meta name=\"twitter:description\" content=\"{html.escape(description)}\" />
  {tw_image_tag}
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
  <link href=\"https://fonts.googleapis.com/css2?family=Newsreader:wght@500;700&family=Source+Sans+3:wght@400;600;700&display=swap\" rel=\"stylesheet\" />
  {json_ld}
"""

    def _html_page(
        self,
        *,
        title: str,
        description: str,
        canonical_path: str,
        body: str,
        og_type: str = "website",
        og_image: str = "",
        json_ld_objects: list[dict] | None = None,
    ) -> str:
        esc_title = html.escape(title)
        seo_head = self._seo_head(
            title=title,
            description=description,
            canonical_path=canonical_path,
            og_type=og_type,
            og_image=og_image,
            json_ld_objects=json_ld_objects,
        )
        return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{esc_title}</title>
  {seo_head}
  <link rel=\"stylesheet\" href=\"{self._href('/assets/site.css')}\" />
  <script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={html.escape(self.adsense_client)}\" crossorigin=\"anonymous\"></script>
</head>
<body>
  <main>
    {body}
    <p class=\"footer-note\">{html.escape(PROJECT_TITLE)} · {html.escape(PROJECT_TAGLINE)}</p>
  </main>
</body>
</html>
"""

    def _post_card(self, post: PublishedBrief) -> str:
        image = post.primary_image or f"/assets/covers/{post.category}.svg"
        category_label = CATEGORY_LABELS.get(post.category, post.category)
        return f"""
<article class=\"story-card\">
  <a class=\"story-media\" href=\"{html.escape(self._href(post.path))}\">
    <img src=\"{html.escape(self._href(image) if image.startswith('/') else image)}\" alt=\"\" loading=\"lazy\" width=\"640\" height=\"360\" />
  </a>
  <div class=\"story-body\">
    <h3 class=\"story-title\"><a href=\"{html.escape(self._href(post.path))}\">{html.escape(post.title)}</a></h3>
    <p class=\"story-summary\">{html.escape(post.meta_description or PROJECT_TAGLINE)}</p>
    <p class=\"meta-line\">{html.escape(category_label)} · {html.escape(post.published_at)}</p>
  </div>
</article>
"""

    def _render_post_html(self, brief: GeneratedBrief, published: PublishedBrief, internal_links: list[PublishedBrief]) -> str:
        payload = brief.payload
        category_label = CATEGORY_LABELS.get(brief.topic.category, brief.topic.category)
        hero = str(payload.get("hero_image_url") or published.primary_image or f"/assets/covers/{brief.topic.category}.svg")
        hero_src = self._href(hero) if hero.startswith("/") else hero

        key_points = "".join([f"<li>{html.escape(one)}</li>" for one in payload.get("key_points") or []])
        deep_dive = "".join([f"<p>{html.escape(one)}</p>" for one in payload.get("deep_dive") or []])
        implications = "".join([f"<p>{html.escape(one)}</p>" for one in payload.get("implications") or []])
        faq_items = "".join(
            [f"<li><strong>{html.escape(one['q'])}</strong> {html.escape(one['a'])}</li>" for one in payload.get("faq") or []]
        )
        src_items = "".join(
            [
                f"<li><a href=\"{html.escape(url)}\" target=\"_blank\" rel=\"noopener\">{html.escape(url)}</a></li>"
                for url in payload.get("source_urls") or []
            ]
        )
        related_cards = "".join([self._post_card(one) for one in internal_links[:6]])

        disclaimer = ""
        if payload.get("disclaimer"):
            disclaimer = f"<p><em>{html.escape(str(payload['disclaimer']))}</em></p>"

        article_schema = payload.get("json_ld") if isinstance(payload.get("json_ld"), dict) else {}
        article_schema = dict(article_schema)
        article_schema["url"] = self._public_url(published.path)
        article_schema["mainEntityOfPage"] = self._public_url(published.path)
        article_schema["image"] = [self._public_url(hero)]
        article_schema["headline"] = payload.get("title") or published.title
        article_schema["description"] = payload.get("meta_description") or published.meta_description
        article_schema["datePublished"] = published.published_at
        article_schema["dateModified"] = published.published_at
        article_schema["articleSection"] = category_label

        breadcrumb_schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": self._public_url('/index.html')},
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": category_label,
                    "item": self._public_url(f"/category/{brief.topic.category}/index.html"),
                },
                {"@type": "ListItem", "position": 3, "name": published.title, "item": self._public_url(published.path)},
            ],
        }

        body = f"""
<header class=\"hero\">
  <span class=\"header-kicker\">{html.escape(category_label)}</span>
  <h1>{html.escape(payload.get('title') or published.title)}</h1>
  <p>{html.escape(published.published_at)} · {int(payload.get('reading_time') or max(1, round(published.word_count / 220)))} min read</p>
</header>
{self._ad_slot('top-banner')}
<article class=\"article\">
  <img class=\"hero-image\" src=\"{html.escape(hero_src)}\" alt=\"{html.escape(str(payload.get('hero_image_alt') or payload.get('title') or published.title))}\" loading=\"eager\" width=\"1200\" height=\"675\" />
  {disclaimer}
  <h2>TL;DR</h2>
  <p>{html.escape(str(payload.get('summary') or ''))}</p>
  <h2>Key Data Points</h2>
  <ul>{key_points}</ul>
  {self._ad_slot('inline-1')}
  <h2>Deep Dive</h2>
  {deep_dive}
  <h2>Implications</h2>
  {implications}
  <h2>Contrarian View</h2>
  <p>{html.escape(str(payload.get('contrarian_view') or ''))}</p>
  <h2>FAQ</h2>
  <ul>{faq_items}</ul>
  <h2>Sources</h2>
  <ul>{src_items}</ul>
  {self._ad_slot('inline-2')}
</article>
<section class=\"panel\">
  <h3>Related Briefs</h3>
  <div class=\"story-grid\">{related_cards or '<p>No related briefs yet.</p>'}</div>
</section>
{self._ad_slot('footer')}
"""

        return self._html_page(
            title=str(payload.get("seo_title") or published.seo_title or published.title),
            description=str(payload.get("meta_description") or published.meta_description or PROJECT_TAGLINE),
            canonical_path=published.path,
            body=body,
            og_type="article",
            og_image=hero,
            json_ld_objects=[article_schema, breadcrumb_schema],
        )

    def _render_home_html(self, posts: list[PublishedBrief]) -> str:
        featured = posts[0] if posts else None
        trending = posts[:5]
        grid_posts = posts[1:19] if len(posts) > 1 else []

        nav = "".join(
            [
                f"<a href=\"{html.escape(self._href(f'/category/{category}/index.html'))}\">{html.escape(CATEGORY_LABELS.get(category, category))}</a>"
                for category in ALL_CATEGORIES
            ]
        )

        if featured:
            featured_image = featured.primary_image or f"/assets/covers/{featured.category}.svg"
            featured_html = f"""
<article class=\"featured\">
  <a class=\"featured-media\" href=\"{html.escape(self._href(featured.path))}\">
    <img src=\"{html.escape(self._href(featured_image) if featured_image.startswith('/') else featured_image)}\" alt=\"\" loading=\"eager\" width=\"1200\" height=\"675\" />
  </a>
  <div class=\"featured-body\">
    <span class=\"header-kicker\">Featured</span>
    <h2><a href=\"{html.escape(self._href(featured.path))}\">{html.escape(featured.title)}</a></h2>
    <p>{html.escape(featured.meta_description or PROJECT_TAGLINE)}</p>
    <p class=\"meta-line\">{html.escape(featured.published_at)}</p>
  </div>
</article>
"""
        else:
            featured_html = "<article class=\"featured\"><div class=\"featured-body\"><h2>No briefs yet.</h2></div></article>"

        trending_html = "".join(
            [
                f"<li><a href=\"{html.escape(self._href(post.path))}\">{html.escape(post.title)}</a><br /><span class=\"meta-line\">{html.escape(post.published_at)}</span></li>"
                for post in trending
            ]
        )

        cards = "".join([self._post_card(post) for post in grid_posts])

        website_schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": PROJECT_TITLE,
            "url": self.site_url,
            "inLanguage": "en",
            "description": PROJECT_TAGLINE,
        }
        org_schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": PROJECT_TITLE,
            "url": self.site_url,
        }

        body = f"""
<header class=\"hero\">
  <span class=\"header-kicker\">Automated Trend Media</span>
  <h1>{html.escape(PROJECT_TITLE)}</h1>
  <p>{html.escape(PROJECT_TAGLINE)}</p>
</header>
<nav class=\"categories\">{nav}</nav>
<div class=\"layout-grid\">
  {featured_html}
  <aside class=\"trending\">
    <h3>Trending This Week</h3>
    <ol>{trending_html or '<li>No trending stories yet.</li>'}</ol>
  </aside>
</div>
{self._ad_slot('top-banner')}
<section>
  <div class=\"story-grid\">{cards or '<p>No briefs yet.</p>'}</div>
</section>
"""

        return self._html_page(
            title=PROJECT_TITLE,
            description=PROJECT_TAGLINE,
            canonical_path="/index.html",
            body=body,
            og_image="/assets/covers/general.svg",
            json_ld_objects=[website_schema, org_schema],
        )

    def _render_category_html(self, category: str, posts: list[PublishedBrief]) -> str:
        category_label = CATEGORY_LABELS.get(category, category)
        cards = "".join([self._post_card(post) for post in posts[:30]])
        top = posts[0] if posts else None

        top_html = ""
        if top:
            top_html = f"<p class=\"meta-line\">Top story: <a href=\"{html.escape(self._href(top.path))}\">{html.escape(top.title)}</a></p>"

        collection_schema = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{category_label} Briefings",
            "url": self._public_url(f"/category/{category}/index.html"),
            "isPartOf": self._public_url("/index.html"),
            "inLanguage": "en",
        }

        body = f"""
<header class=\"hero\">
  <span class=\"header-kicker\">Category</span>
  <h1>{html.escape(category_label)}</h1>
  <p><a href=\"{html.escape(self._href('/index.html'))}\">Back to home</a></p>
  {top_html}
</header>
{self._ad_slot('top-banner')}
<section>
  <div class=\"story-grid\">{cards or '<p>No stories yet.</p>'}</div>
</section>
"""

        return self._html_page(
            title=f"{category_label} · {PROJECT_TITLE}",
            description=f"Latest {category_label} trend briefings from {PROJECT_TITLE}.",
            canonical_path=f"/category/{category}/index.html",
            body=body,
            og_image=f"/assets/covers/{category}.svg",
            json_ld_objects=[collection_schema],
        )

    def _render_robots(self) -> str:
        return "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                f"Sitemap: {self.site_url}/sitemap.xml",
                "",
            ]
        )

    def _render_sitemap(self, posts: list[PublishedBrief]) -> str:
        rows: list[tuple[str, str]] = [(f"{self.site_url}/index.html", datetime.now().date().isoformat())]

        by_category: dict[str, str] = {}
        for post in posts:
            post_url = f"{self.site_url}{post.path}"
            lastmod = str(post.published_at)[:10]
            rows.append((post_url, lastmod))
            current = by_category.get(post.category, "")
            if lastmod > current:
                by_category[post.category] = lastmod

        for category in ALL_CATEGORIES:
            rows.append((f"{self.site_url}/category/{category}/index.html", by_category.get(category, "")))

        entries = "\n".join(
            [
                f"  <url><loc>{html.escape(url)}</loc>{f'<lastmod>{html.escape(lastmod)}</lastmod>' if lastmod else ''}</url>"
                for url, lastmod in rows
            ]
        )
        return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
{entries}
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
                        f"    <description>{html.escape(post.meta_description or PROJECT_TAGLINE)}</description>",
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
