#!/usr/bin/env python3
"""CLI entrypoint for Signal Atlas ops report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from signal_atlas.report import build_ops_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show Signal Atlas operational report")
    parser.add_argument("--window", default="24h", help="Examples: 24h, 72h, 7d")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--state-file", default="state/pipeline_state.json")
    parser.add_argument("--metrics-file", default="state/ops_metrics.jsonl")
    return parser.parse_args()


def _text_report(report: dict) -> str:
    lines = [
        f"Window: {report['window']}",
        f"Samples: {report['samples']}",
        f"Publish Limit: {report['publish_limit']}",
        f"Disabled Verticals: {', '.join(report['disabled_verticals']) or 'none'}",
        "Averages:",
        f"  indexed_rate={report['averages']['indexed_rate']}",
        f"  duplicate_rate={report['averages']['duplicate_rate']}",
        f"  policy_flag_rate={report['averages']['policy_flag_rate']}",
        f"  rpm_estimate={report['averages']['rpm_estimate']}",
        f"  publish_count={report['averages']['publish_count']}",
    ]

    latest = report.get("latest")
    if latest:
        lines.append("Latest:")
        lines.append(f"  timestamp={latest.get('timestamp')}")
        lines.append(f"  indexed_rate={latest.get('indexed_rate')}")
        lines.append(f"  duplicate_rate={latest.get('duplicate_rate')}")
        lines.append(f"  policy_flag_rate={latest.get('policy_flag_rate')}")
        lines.append(f"  rpm_estimate={latest.get('rpm_estimate')}")
        lines.append(f"  publish_count={latest.get('publish_count')}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent

    report = build_ops_report(
        state_file=str(root / args.state_file),
        metrics_file=str(root / args.metrics_file),
        window=args.window,
    )

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_text_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
