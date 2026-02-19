"""State persistence and scaling utilities."""

from __future__ import annotations

from datetime import datetime

from .constants import (
    ALL_VERTICALS,
    DEFAULT_PUBLISH_LIMIT,
    MAX_DAILY_HISTORY,
    MAX_PUBLISHED_HISTORY,
    PUBLISH_STAGES,
    SCALE_RULES,
    TARGET_TIMEZONE,
)
from .utils import append_jsonl, read_json, read_jsonl, write_json


def default_state(now_iso: str) -> dict:
    return {
        "version": 1,
        "timezone": TARGET_TIMEZONE,
        "created_at": now_iso,
        "updated_at": now_iso,
        "publish_limit": DEFAULT_PUBLISH_LIMIT,
        "disabled_verticals": [],
        "vertical_deploy_failures": {v: 0 for v in ALL_VERTICALS},
        "published": [],
        "daily_history": [],
    }


def load_state(path: str, now_iso: str) -> dict:
    state = read_json(path, default={})
    if not state:
        return default_state(now_iso)

    merged = default_state(now_iso)
    merged.update(state)

    # Ensure mandatory keys are always present.
    merged.setdefault("disabled_verticals", [])
    merged.setdefault("published", [])
    merged.setdefault("daily_history", [])
    merged.setdefault("publish_limit", DEFAULT_PUBLISH_LIMIT)

    vdf = merged.get("vertical_deploy_failures") or {}
    merged["vertical_deploy_failures"] = {v: int(vdf.get(v, 0)) for v in ALL_VERTICALS}

    merged["publish_limit"] = int(merged.get("publish_limit") or DEFAULT_PUBLISH_LIMIT)
    merged["updated_at"] = now_iso
    return merged


def save_state(path: str, state: dict) -> None:
    write_json(path, state)


def append_metrics(path: str, metrics: dict) -> None:
    append_jsonl(path, metrics)


def load_metrics(path: str) -> list[dict]:
    return read_jsonl(path)


def upsert_daily_history(state: dict, entry: dict) -> None:
    rows = state.get("daily_history") or []
    if rows and rows[-1].get("date") == entry.get("date"):
        rows[-1] = entry
    else:
        rows.append(entry)

    if len(rows) > MAX_DAILY_HISTORY:
        rows[:] = rows[-MAX_DAILY_HISTORY:]

    state["daily_history"] = rows


def trim_published_history(state: dict) -> None:
    rows = state.get("published") or []
    if len(rows) > MAX_PUBLISHED_HISTORY:
        state["published"] = rows[-MAX_PUBLISHED_HISTORY:]


def maybe_scale_publish_limit(state: dict) -> int | None:
    """Promote publish limit (12->18->24) if 7-day quality streak is met."""
    current = int(state.get("publish_limit") or DEFAULT_PUBLISH_LIMIT)
    if current >= PUBLISH_STAGES[-1]:
        return None

    days = int(SCALE_RULES["days"])
    history = state.get("daily_history") or []
    if len(history) < days:
        return None

    window = history[-days:]
    for row in window:
        if float(row.get("duplicate_rate", 1.0)) >= float(SCALE_RULES["duplicate_rate_max"]):
            return None
        if float(row.get("policy_flag_rate", 1.0)) >= float(SCALE_RULES["policy_flag_rate_max"]):
            return None
        if float(row.get("indexed_rate", 0.0)) < float(SCALE_RULES["indexed_rate_min"]):
            return None

    next_stage = current
    for stage in PUBLISH_STAGES:
        if stage > current:
            next_stage = stage
            break

    if next_stage != current:
        state["publish_limit"] = next_stage
        return next_stage

    return None


def filter_metrics_by_window(rows: list[dict], window_hours: int, now: datetime) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        ts = row.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(str(ts))
        except ValueError:
            continue

        delta_hours = (now - dt).total_seconds() / 3600.0
        if delta_hours <= float(window_hours):
            out.append(row)
    return out
