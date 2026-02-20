#!/usr/bin/env python3
"""CLI entrypoint for running Signal Atlas pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from signal_atlas.constants import ALL_VERTICALS, DEFAULT_URL_SCHEMA, THEME_MAGAZINE_V2
from signal_atlas.pipeline import Pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Signal Atlas pipeline")
    parser.add_argument("--vertical", choices=["all", *ALL_VERTICALS], default="all")
    parser.add_argument("--max-publish", type=int, default=None)
    parser.add_argument("--mode", choices=["production", "dry-run"], default="production")
    parser.add_argument("--generation-engine", choices=["gemini", "template"], default="gemini")
    parser.add_argument("--quality-tier", choices=["premium", "balanced"], default="premium")
    parser.add_argument("--url-schema", choices=["v1", "v2"], default=DEFAULT_URL_SCHEMA)
    parser.add_argument("--theme-variant", default=THEME_MAGAZINE_V2)
    parser.add_argument("--state-file", default="state/pipeline_state.json")
    parser.add_argument("--metrics-file", default="state/ops_metrics.jsonl")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--site-dir", default="site")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent

    pipeline = Pipeline(
        state_file=str(root / args.state_file),
        metrics_file=str(root / args.metrics_file),
        artifacts_dir=str(root / args.artifacts_dir),
        site_dir=str(root / args.site_dir),
        url_schema=args.url_schema,
        theme_variant=args.theme_variant,
    )
    summary = pipeline.run(
        vertical=args.vertical,
        max_publish=args.max_publish,
        mode=args.mode,
        generation_engine=args.generation_engine,
        quality_tier=args.quality_tier,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
