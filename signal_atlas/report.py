"""Operational reporting helpers."""

from __future__ import annotations

from datetime import datetime

from .constants import DEFAULT_PUBLISH_LIMIT
from .state import filter_metrics_by_window, load_metrics, load_state
from .utils import parse_window_hours


def build_ops_report(state_file: str, metrics_file: str, window: str, now: datetime | None = None) -> dict:
    now = now or datetime.now().astimezone()
    now_iso = now.isoformat(timespec="seconds")

    window_hours = parse_window_hours(window)
    state = load_state(state_file, now_iso=now_iso)

    all_rows = load_metrics(metrics_file)
    rows = filter_metrics_by_window(all_rows, window_hours=window_hours, now=now)

    if not rows:
        return {
            "window": f"{window_hours}h",
            "samples": 0,
            "disabled_verticals": state.get("disabled_verticals") or [],
            "publish_limit": int(state.get("publish_limit") or DEFAULT_PUBLISH_LIMIT),
            "latest": None,
            "averages": {
                "indexed_rate": 0.0,
                "duplicate_rate": 0.0,
                "policy_flag_rate": 0.0,
                "rpm_estimate": 0.0,
                "publish_count": 0.0,
            },
        }

    def _avg(key: str) -> float:
        return round(sum(float(r.get(key) or 0.0) for r in rows) / len(rows), 4)

    latest = rows[-1]
    return {
        "window": f"{window_hours}h",
        "samples": len(rows),
        "disabled_verticals": state.get("disabled_verticals") or [],
        "publish_limit": int(state.get("publish_limit") or DEFAULT_PUBLISH_LIMIT),
        "latest": latest,
        "averages": {
            "indexed_rate": _avg("indexed_rate"),
            "duplicate_rate": _avg("duplicate_rate"),
            "policy_flag_rate": _avg("policy_flag_rate"),
            "rpm_estimate": _avg("rpm_estimate"),
            "publish_count": _avg("publish_count"),
        },
    }
