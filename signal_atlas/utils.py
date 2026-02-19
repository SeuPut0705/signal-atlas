"""Shared utility helpers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .constants import TARGET_TIMEZONE


def now_tz() -> datetime:
    return datetime.now(ZoneInfo(TARGET_TIMEZONE))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: str | Path, default: dict | list | None = None):
    p = Path(path)
    if not p.exists():
        if default is None:
            raise FileNotFoundError(str(path))
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, payload: dict | list) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(p)


def append_jsonl(path: str | Path, payload: dict) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 80) -> str:
    out = _slug_re.sub("-", text.lower()).strip("-")
    if not out:
        out = "brief"
    return out[:max_len].strip("-")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def stable_hash(text: str, n: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def dedupe_hash(text: str) -> str:
    return stable_hash(normalize_text(text), n=24)


def parse_window_hours(raw: str) -> int:
    raw = raw.strip().lower()
    if raw.endswith("h"):
        return int(raw[:-1])
    if raw.endswith("d"):
        return int(raw[:-1]) * 24
    return int(raw)
