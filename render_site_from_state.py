#!/usr/bin/env python3
"""Re-render static site from archived published rows without creating new posts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from signal_atlas.constants import DEFAULT_URL_SCHEMA, THEME_MAGAZINE_V2
from signal_atlas.publish import StaticSitePublisher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-render Signal Atlas site from pipeline state")
    parser.add_argument("--state-file", default="state/pipeline_state.json")
    parser.add_argument("--site-dir", default="site")
    parser.add_argument("--site-url", default=None)
    parser.add_argument("--url-schema", choices=["v1", "v2"], default=DEFAULT_URL_SCHEMA)
    parser.add_argument("--theme-variant", default=THEME_MAGAZINE_V2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    state_path = root / args.state_file
    site_dir = root / args.site_dir

    if not state_path.exists():
        raise SystemExit(f"State file not found: {state_path}")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    rows = list(state.get("published") or [])

    publisher = StaticSitePublisher(
        site_dir=str(site_dir),
        site_url=args.site_url,
        url_schema=args.url_schema,
        theme_variant=args.theme_variant,
    )
    publisher.publish(
        generated_briefs=[],
        existing_rows=rows,
        now_iso=datetime.now().astimezone().isoformat(),
    )
    print(json.dumps({"rendered_posts": len(rows), "site_dir": str(site_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
