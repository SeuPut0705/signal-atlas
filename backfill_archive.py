#!/usr/bin/env python3
"""Backfill and regenerate archived Signal Atlas posts with latest templates/SEO."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from signal_atlas.constants import DEFAULT_URL_SCHEMA, STORY_PATH_PATTERN_V2, THEME_MAGAZINE_V2
from signal_atlas.content import build_generated_brief
from signal_atlas.models import ApprovedTopic, SourceMeta
from signal_atlas.publish import StaticSitePublisher
from signal_atlas.utils import isoformat, stable_hash, write_json


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _normalize_source_meta(row: dict, source_urls: list[str]) -> list[SourceMeta]:
    out: list[SourceMeta] = []
    for raw in row.get("source_meta") or []:
        if not isinstance(raw, dict):
            continue
        out.append(
            SourceMeta(
                url=str(raw.get("url") or ""),
                title=str(raw.get("title") or ""),
                description=str(raw.get("description") or ""),
                image=str(raw.get("image") or ""),
                site_name=str(raw.get("site_name") or ""),
            )
        )
    if out:
        return out
    for url in source_urls[:3]:
        out.append(SourceMeta(url=url))
    return out


def _row_to_topic(row: dict, idx: int, now_iso: str) -> ApprovedTopic:
    title = str(row.get("title") or "").strip()
    if not title:
        raise ValueError("missing title")

    raw_urls = row.get("source_urls") or []
    source_urls: list[str] = []
    for one in raw_urls:
        one_url = str(one or "").strip()
        if one_url and one_url not in source_urls:
            source_urls.append(one_url)
    if not source_urls:
        source_urls = [f"https://example.com/backfill/{idx}"]

    category = str(row.get("category") or row.get("subcategory") or "general").strip() or "general"
    discovered_at = str(row.get("published_at") or row.get("discovered_at") or now_iso)
    dedupe = str(row.get("dedupe_hash") or stable_hash(title, n=24))

    return ApprovedTopic(
        id=str(row.get("id") or stable_hash(f"backfill|{row.get('path') or title}|{idx}", n=24)),
        vertical=str(row.get("vertical") or "ai_tech"),
        category=category,
        title=title,
        source_urls=source_urls,
        discovered_at=discovered_at,
        confidence_score=float(row.get("confidence_score") or 0.8),
        policy_score=float(row.get("policy_score") or 0.95),
        dedupe_hash=dedupe,
        policy_flags=list(row.get("policy_flags") or []),
        snippet=str(row.get("snippet") or row.get("meta_description") or ""),
        source_meta=_normalize_source_meta(row, source_urls),
    )


def _merge_rows(existing_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in existing_rows:
        path = str(row.get("path") or "")
        if path:
            merged[path] = dict(row)
    for row in new_rows:
        path = str(row.get("path") or "")
        if path:
            incoming = dict(row)
            prior = merged.get(path) or {}
            legacy = list(prior.get("legacy_paths") or []) + list(incoming.get("legacy_paths") or [])
            dedup_legacy: list[str] = []
            for one in legacy:
                item = str(one or "").strip()
                if item and item not in dedup_legacy and item != path:
                    dedup_legacy.append(item)
            incoming["legacy_paths"] = dedup_legacy
            merged[path] = incoming
    rows = list(merged.values())
    rows.sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill archived posts with latest generation and templates.")
    parser.add_argument("--scope", choices=["all"], default="all")
    parser.add_argument("--generation-engine", choices=["gemini", "template"], default="gemini")
    parser.add_argument("--quality-tier", choices=["premium", "balanced"], default="premium")
    parser.add_argument("--url-schema", choices=["v1", "v2"], default=DEFAULT_URL_SCHEMA)
    parser.add_argument("--theme-variant", default=THEME_MAGAZINE_V2)
    parser.add_argument("--state-file", default="state/pipeline_state.json")
    parser.add_argument("--site-dir", default="site")
    parser.add_argument("--checkpoint-file", default="state/backfill_checkpoint.json")
    parser.add_argument("--restart", action="store_true", help="Ignore checkpoint and restart from index 0")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    state_file = (root / args.state_file).resolve()
    site_dir = (root / args.site_dir).resolve()
    checkpoint_file = (root / args.checkpoint_file).resolve()

    state = _load_json(state_file, default={})
    rows = list(state.get("published") or [])
    total = len(rows)

    now = datetime.now().astimezone()
    now_iso = isoformat(now)

    checkpoint = _load_json(checkpoint_file, default={})
    start_index = 0
    if not args.restart and isinstance(checkpoint, dict):
        if str(checkpoint.get("scope") or "all") == args.scope:
            start_index = int(checkpoint.get("next_index") or 0)
    start_index = max(0, min(start_index, total))

    generated = []
    failures: list[dict] = []
    for idx in range(start_index, total):
        row = rows[idx]
        try:
            topic = _row_to_topic(row, idx, now_iso)
            brief = build_generated_brief(
                topic,
                generation_engine=args.generation_engine,
                quality_tier=args.quality_tier,
            )
            generated.append(brief)
        except Exception as exc:  # pragma: no cover - defensive guard for long-running backfills.
            failures.append({"index": idx, "path": str(row.get("path") or ""), "error": str(exc)})
        checkpoint_payload = {
            "scope": args.scope,
            "url_schema": args.url_schema,
            "next_index": idx + 1,
            "total": total,
            "updated_at": now_iso,
            "completed": False,
        }
        write_json(checkpoint_file, checkpoint_payload)

    publisher = StaticSitePublisher(
        site_dir=str(site_dir),
        url_schema=args.url_schema,
        theme_variant=args.theme_variant,
    )
    published_rows: list[dict] = []
    if generated:
        published = publisher.publish(
            generated_briefs=generated,
            existing_rows=rows,
            now_iso=now_iso,
        )
        published_rows = []
        for row in published:
            payload = row.to_dict()
            old_path = str(payload.get("path") or "")
            if args.url_schema == "v2":
                payload["path"] = STORY_PATH_PATTERN_V2.format(category=row.category, slug=row.slug)
            if old_path and old_path != payload["path"]:
                legacy = list(payload.get("legacy_paths") or [])
                if old_path not in legacy:
                    legacy.append(old_path)
                payload["legacy_paths"] = legacy
            payload["url_schema"] = args.url_schema
            payload["template_version"] = args.theme_variant
            published_rows.append(payload)
        state["published"] = _merge_rows(rows, published_rows)
        state["updated_at"] = now_iso
        state["backfill"] = {
            "last_run_at": now_iso,
            "scope": args.scope,
            "generation_engine": args.generation_engine,
            "quality_tier": args.quality_tier,
            "url_schema": args.url_schema,
            "theme_variant": args.theme_variant,
            "processed": total - start_index,
            "regenerated": len(published_rows),
            "failures": len(failures),
        }
        write_json(state_file, state)

    write_json(
        checkpoint_file,
        {
            "scope": args.scope,
            "url_schema": args.url_schema,
            "next_index": total,
            "total": total,
            "updated_at": now_iso,
            "completed": True,
            "completed_at": now_iso,
        },
    )

    summary = {
        "scope": args.scope,
        "state_file": str(state_file),
        "site_dir": str(site_dir),
        "checkpoint_file": str(checkpoint_file),
        "start_index": start_index,
        "total": total,
        "processed": total - start_index,
        "regenerated": len(published_rows),
        "failures": len(failures),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
