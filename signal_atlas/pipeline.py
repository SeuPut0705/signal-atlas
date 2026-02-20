"""Main orchestration pipeline for Signal Atlas."""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .constants import (
    ALL_CATEGORIES,
    ALL_VERTICALS,
    DEFAULT_URL_SCHEMA,
    DEFAULT_CATEGORY,
    DEFAULT_PUBLISH_LIMIT,
    DEPLOY_FAILURE_DISABLE_COUNT,
    LEGACY_CATEGORY_MAP,
    POLICY_DISABLE_RATE,
    STORY_PATH_PATTERN_V2,
    THEME_MAGAZINE_V2,
)
from .content import build_generated_brief
from .ingest import Ingestor
from .metrics import build_ops_metrics
from .publish import StaticSitePublisher
from .rank import approve_topics
from .state import append_metrics, load_state, maybe_scale_publish_limit, save_state, trim_published_history, upsert_daily_history
from .utils import ensure_dir, isoformat, write_json

BUDGET_ALERT_RATIO = 0.85
PREMIUM_EST_KRW = 220.0
BALANCED_EST_KRW = 120.0


class Pipeline:
    def __init__(
        self,
        *,
        state_file: str,
        metrics_file: str,
        artifacts_dir: str,
        site_dir: str,
        url_schema: str | None = None,
        theme_variant: str | None = None,
        ingestor: Ingestor | None = None,
        publisher: StaticSitePublisher | None = None,
    ):
        self.state_file = state_file
        self.metrics_file = metrics_file
        self.artifacts_dir = artifacts_dir
        self.site_dir = site_dir
        self.url_schema = str(url_schema or os.getenv("URL_SCHEMA") or DEFAULT_URL_SCHEMA)
        self.theme_variant = str(theme_variant or os.getenv("THEME_VARIANT") or THEME_MAGAZINE_V2)
        self.ingestor = ingestor or Ingestor()
        self.publisher = publisher or StaticSitePublisher(
            site_dir=site_dir,
            url_schema=self.url_schema,
            theme_variant=self.theme_variant,
        )

    def run(
        self,
        *,
        vertical: str,
        max_publish: int | None,
        mode: str,
        generation_engine: str | None = None,
        quality_tier: str | None = None,
        now: datetime | None = None,
    ) -> dict:
        now = now or datetime.now().astimezone()
        now_iso = isoformat(now)
        generation_engine_requested = self._normalize_generation_engine(
            generation_engine or os.getenv("GENERATION_ENGINE") or "gemini"
        )
        quality_tier_requested = self._normalize_quality_tier(
            quality_tier or os.getenv("QUALITY_TIER") or "premium"
        )
        gemini_model = (os.getenv("GEMINI_MODEL") or "gemini-2.5-pro").strip() or "gemini-2.5-pro"
        budget_limit_krw = max(1, int(float(os.getenv("MONTHLY_BUDGET_KRW") or 200000)))

        state = load_state(self.state_file, now_iso=now_iso)
        self._migrate_published_category(state)
        budget = self._load_budget_state(state, now)
        budget["limit_krw"] = budget_limit_krw
        disabled = set(state.get("disabled_verticals") or [])

        requested_verticals = self._resolve_verticals(vertical)
        active_verticals = [v for v in requested_verticals if v not in disabled]

        publish_limit = int(max_publish or state.get("publish_limit") or DEFAULT_PUBLISH_LIMIT)
        quotas = self._allocate_quota(active_verticals, publish_limit)

        all_generated = []
        existing_history = list(state.get("published") or [])

        candidate_count = 0
        duplicate_count = 0
        policy_flag_count = 0

        per_vertical: dict[str, dict] = {}
        source_failures: dict[str, int] = {}
        generation_counts: dict[str, int] = defaultdict(int)

        for one_vertical in active_verticals:
            candidates, ingest_meta = self.ingestor.collect(
                one_vertical,
                now=now,
                max_candidates=max(20, quotas[one_vertical] * 5),
            )
            approved, stats = approve_topics(
                candidates,
                history_rows=existing_history,
                max_count=quotas[one_vertical],
            )

            generated = []
            vertical_generation_counts: dict[str, int] = defaultdict(int)
            for topic in approved:
                effective_engine, effective_quality = self._choose_generation_mode(
                    requested_engine=generation_engine_requested,
                    requested_quality=quality_tier_requested,
                    budget=budget,
                )

                brief = build_generated_brief(
                    topic,
                    generation_engine=effective_engine,
                    quality_tier=effective_quality,
                    gemini_model=gemini_model,
                )
                generated.append(brief)

                engine_used = str(brief.payload.get("generation_engine") or effective_engine)
                generation_counts[engine_used] += 1
                vertical_generation_counts[engine_used] += 1
                self._apply_generation_cost_to_budget(budget, brief.payload)

            all_generated.extend(generated)

            existing_history.extend(
                [
                    {
                        "title": topic.title,
                        "dedupe_hash": topic.dedupe_hash,
                        "category": topic.category,
                    }
                    for topic in approved
                ]
            )

            candidate_count += stats.candidate_count
            duplicate_count += stats.duplicate_count
            policy_flag_count += stats.policy_flag_count

            source_failures[one_vertical] = ingest_meta.source_failures
            per_vertical[one_vertical] = {
                "candidate_count": stats.candidate_count,
                "duplicate_count": stats.duplicate_count,
                "policy_flag_count": stats.policy_flag_count,
                "blocked_count": stats.blocked_count,
                "approved_count": len(approved),
                "generated_count": len(generated),
                "source_failures": ingest_meta.source_failures,
                "used_fallback": ingest_meta.used_fallback,
                "generation_usage": dict(vertical_generation_counts),
            }

        run_artifacts = self._write_artifacts(all_generated, now=now, mode=mode)

        publish_counts = defaultdict(int)
        published_rows: list[dict] = []

        deploy_attempts = 0
        deploy_error = ""

        if mode == "production" and all_generated:
            for attempt in range(1, 4):
                deploy_attempts = attempt
                try:
                    published = self.publisher.publish(
                        generated_briefs=all_generated,
                        existing_rows=state.get("published") or [],
                        now_iso=now_iso,
                    )
                    for row in published:
                        publish_counts[row.vertical] += 1
                        published_rows.append(row.to_dict())
                    deploy_error = ""
                    break
                except Exception as exc:  # pragma: no cover - exercised by integration test via custom publisher.
                    deploy_error = str(exc)

            if not published_rows:
                # Deploy failed after retries: increase failure streak and auto-disable at threshold.
                for vertical_name, count in self._count_generated_by_vertical(all_generated).items():
                    if count <= 0:
                        continue
                    failure_map = state.setdefault("vertical_deploy_failures", {})
                    failure_map[vertical_name] = int(failure_map.get(vertical_name, 0)) + 1
                    if int(failure_map[vertical_name]) >= DEPLOY_FAILURE_DISABLE_COUNT:
                        disabled.add(vertical_name)
            else:
                failure_map = state.setdefault("vertical_deploy_failures", {})
                for vertical_name in publish_counts:
                    failure_map[vertical_name] = 0
                state["published"] = self._merge_published_rows(state.get("published") or [], published_rows)
                trim_published_history(state)

        elif mode == "dry-run":
            for vertical_name, count in self._count_generated_by_vertical(all_generated).items():
                publish_counts[vertical_name] += count

        # Policy safety auto-disable.
        for vertical_name, stats in per_vertical.items():
            rate = float(stats["policy_flag_count"]) / max(1, int(stats["candidate_count"]))
            if rate >= POLICY_DISABLE_RATE:
                disabled.add(vertical_name)

        state["disabled_verticals"] = sorted(disabled)
        self._save_budget_state(state, budget)

        total_publish = sum(publish_counts.values())
        ops_metrics = build_ops_metrics(
            timestamp=now_iso,
            candidate_count=candidate_count,
            duplicate_count=duplicate_count,
            policy_flag_count=policy_flag_count,
            publish_count=total_publish,
            vertical_publish_counts=dict(publish_counts),
        )

        daily_entry = {
            "date": now.date().isoformat(),
            "duplicate_rate": ops_metrics.duplicate_rate,
            "policy_flag_rate": ops_metrics.policy_flag_rate,
            "indexed_rate": ops_metrics.indexed_rate,
            "rpm_estimate": ops_metrics.rpm_estimate,
            "publish_count": ops_metrics.publish_count,
        }
        upsert_daily_history(state, daily_entry)

        scaled_to = maybe_scale_publish_limit(state)

        state["updated_at"] = now_iso
        save_state(self.state_file, state)
        append_metrics(self.metrics_file, ops_metrics.to_dict())

        return {
            "mode": mode,
            "timestamp": now_iso,
            "requested_verticals": requested_verticals,
            "active_verticals": active_verticals,
            "disabled_verticals": state["disabled_verticals"],
            "publish_limit_requested": publish_limit,
            "publish_limit_effective": int(state.get("publish_limit") or DEFAULT_PUBLISH_LIMIT),
            "publish_limit_scaled_to": scaled_to,
            "candidates": candidate_count,
            "duplicates": duplicate_count,
            "policy_flags": policy_flag_count,
            "published": total_publish,
            "per_vertical": per_vertical,
            "source_failures": source_failures,
            "deploy_attempts": deploy_attempts,
            "deploy_error": deploy_error,
            "generation_engine_requested": generation_engine_requested,
            "quality_tier_requested": quality_tier_requested,
            "generation_usage": dict(generation_counts),
            "budget": state.get("budget") or {},
            "metrics": ops_metrics.to_dict(),
            "artifacts": run_artifacts,
            "state_file": self.state_file,
            "metrics_file": self.metrics_file,
            "url_schema": self.url_schema,
            "theme_variant": self.theme_variant,
        }

    def _resolve_verticals(self, vertical: str) -> list[str]:
        if vertical == "all":
            return list(ALL_VERTICALS)
        if vertical not in ALL_VERTICALS:
            raise ValueError(f"Unsupported vertical: {vertical}")
        return [vertical]

    def _allocate_quota(self, verticals: list[str], publish_limit: int) -> dict[str, int]:
        if not verticals:
            return {}
        if len(verticals) == 1:
            return {verticals[0]: max(1, int(publish_limit))}

        total = max(len(verticals), int(publish_limit))
        base = total // len(verticals)
        remainder = total % len(verticals)

        out: dict[str, int] = {}
        for idx, one_vertical in enumerate(verticals):
            out[one_vertical] = base + (1 if idx < remainder else 0)
        return out

    def _count_generated_by_vertical(self, generated) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for one in generated:
            counts[one.topic.vertical] += 1
        return counts

    def _write_artifacts(self, generated_briefs, now: datetime, mode: str) -> dict:
        run_dir = Path(self.artifacts_dir) / now.date().isoformat()
        ensure_dir(run_dir)

        files = []
        for brief in generated_briefs:
            category_dir = run_dir / brief.topic.category
            ensure_dir(category_dir)

            md_path = category_dir / f"{brief.slug}.md"
            json_path = category_dir / f"{brief.slug}.json"

            md_path.write_text(brief.markdown, encoding="utf-8")
            write_json(json_path, brief.to_dict())
            files.append(str(md_path))
            files.append(str(json_path))

        return {
            "run_dir": str(run_dir),
            "mode": mode,
            "file_count": len(files),
        }

    def _merge_published_rows(self, existing_rows: list[dict], new_rows: list[dict]) -> list[dict]:
        merged: dict[str, dict] = {}
        for row in existing_rows:
            path = str(row.get("path") or "")
            if not path:
                continue
            merged[path] = dict(row)
        for row in new_rows:
            path = str(row.get("path") or "")
            if not path:
                continue
            incoming = dict(row)
            prior = merged.get(path) or {}
            legacy = list(prior.get("legacy_paths") or []) + list(incoming.get("legacy_paths") or [])
            dedup_legacy: list[str] = []
            for item in legacy:
                one = str(item or "").strip()
                if one and one not in dedup_legacy and one != path:
                    dedup_legacy.append(one)
            incoming["legacy_paths"] = dedup_legacy
            merged[path] = incoming

        rows = list(merged.values())
        rows.sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)
        return rows

    def _normalize_generation_engine(self, value: str) -> str:
        value = str(value or "").strip().lower()
        if value not in {"gemini", "template"}:
            return "gemini"
        return value

    def _normalize_quality_tier(self, value: str) -> str:
        value = str(value or "").strip().lower()
        if value not in {"premium", "balanced"}:
            return "premium"
        return value

    def _load_budget_state(self, state: dict, now: datetime) -> dict:
        month = now.strftime("%Y-%m")
        budget = state.get("budget")
        if not isinstance(budget, dict) or budget.get("month") != month:
            budget = {
                "month": month,
                "spent_krw": 0.0,
                "limit_krw": max(1, int(float(os.getenv("MONTHLY_BUDGET_KRW") or 200000))),
                "last_engine": "gemini",
                "last_quality_tier": "premium",
            }
        budget["month"] = month
        budget["spent_krw"] = round(float(budget.get("spent_krw") or 0.0), 2)
        budget["limit_krw"] = max(1, int(float(budget.get("limit_krw") or 200000)))
        return budget

    def _save_budget_state(self, state: dict, budget: dict) -> None:
        spent = round(float(budget.get("spent_krw") or 0.0), 2)
        limit_krw = max(1, int(float(budget.get("limit_krw") or 200000)))
        budget["spent_krw"] = spent
        budget["limit_krw"] = limit_krw
        budget["alert_ratio"] = BUDGET_ALERT_RATIO
        budget["capped"] = spent >= limit_krw
        state["budget"] = budget

        usage = state.get("budget_usage")
        if not isinstance(usage, dict):
            usage = {}
        usage[str(budget.get("month") or "")] = spent
        if len(usage) > 24:
            keep = sorted(usage.keys())[-24:]
            usage = {k: usage[k] for k in keep}
        state["budget_usage"] = usage

    def _choose_generation_mode(self, *, requested_engine: str, requested_quality: str, budget: dict) -> tuple[str, str]:
        if requested_engine == "template":
            budget["last_engine"] = "template"
            budget["last_quality_tier"] = "balanced"
            return "template", "balanced"

        spent = float(budget.get("spent_krw") or 0.0)
        limit_krw = max(1.0, float(budget.get("limit_krw") or 1.0))
        remaining = limit_krw - spent
        quality = requested_quality

        if remaining <= 0:
            budget["last_engine"] = "template"
            budget["last_quality_tier"] = "balanced"
            return "template", "balanced"

        if spent >= limit_krw * BUDGET_ALERT_RATIO and quality == "premium":
            quality = "balanced"

        est_cost = PREMIUM_EST_KRW if quality == "premium" else BALANCED_EST_KRW
        if remaining < est_cost:
            if quality == "premium" and remaining >= BALANCED_EST_KRW:
                quality = "balanced"
            elif remaining < BALANCED_EST_KRW:
                budget["last_engine"] = "template"
                budget["last_quality_tier"] = "balanced"
                return "template", "balanced"

        budget["last_engine"] = "gemini"
        budget["last_quality_tier"] = quality
        return "gemini", quality

    def _apply_generation_cost_to_budget(self, budget: dict, payload: dict) -> None:
        engine = str(payload.get("generation_engine") or "")
        if not engine.startswith("gemini"):
            return
        try:
            cost = max(0.0, float(payload.get("generation_cost_krw") or 0.0))
        except (TypeError, ValueError):
            cost = 0.0
        budget["spent_krw"] = round(float(budget.get("spent_krw") or 0.0) + cost, 2)

    def _migrate_published_category(self, state: dict) -> None:
        """Normalize legacy rows into v2 story paths and preserve legacy paths."""
        rows = state.get("published") or []
        if not rows:
            return

        migrated: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            obj = dict(row)
            vertical = str(obj.get("vertical") or "")
            category = str(obj.get("category") or obj.get("subcategory") or DEFAULT_CATEGORY)
            path = str(obj.get("path") or "")
            legacy_paths = list(obj.get("legacy_paths") or [])

            if vertical not in ALL_VERTICALS:
                if path.startswith("/"):
                    parts = path.strip("/").split("/")
                    if parts:
                        vertical = parts[0]
                if vertical not in ALL_VERTICALS:
                    continue
                obj["vertical"] = vertical

            category = LEGACY_CATEGORY_MAP.get(category, category)
            if not category or category not in set(ALL_CATEGORIES):
                category = DEFAULT_CATEGORY
            obj["category"] = category
            obj.pop("subcategory", None)

            # Keep old path in legacy list before v2 normalization.
            old_path = ""
            if path.startswith("/"):
                parts = path.strip("/").split("/")
                if len(parts) >= 3 and parts[0] == "stories":
                    normalized = LEGACY_CATEGORY_MAP.get(parts[1], parts[1])
                    obj["category"] = normalized if normalized in set(ALL_CATEGORIES) else category
                    obj["path"] = f"/stories/{obj['category']}/{parts[-1]}"
                elif len(parts) >= 3 and parts[0] == "category":
                    normalized = LEGACY_CATEGORY_MAP.get(parts[1], parts[1])
                    obj["category"] = normalized if normalized in set(ALL_CATEGORIES) else category
                    old_path = f"/category/{obj['category']}/{parts[-1]}"
                    obj["path"] = f"/stories/{obj['category']}/{parts[-1]}"
                elif len(parts) >= 3 and parts[0] in ALL_VERTICALS:
                    normalized = LEGACY_CATEGORY_MAP.get(parts[1], parts[1])
                    obj["category"] = normalized if normalized in set(ALL_CATEGORIES) else category
                    old_path = f"/{parts[0]}/{parts[1]}/{parts[-1]}"
                    obj["path"] = f"/stories/{obj['category']}/{parts[-1]}"
                elif len(parts) == 2 and parts[0] in ALL_VERTICALS:
                    old_path = f"/{parts[0]}/{parts[1]}"
                    obj["path"] = f"/stories/{category}/{parts[1]}"
                else:
                    slug = str(obj.get("slug") or "").strip()
                    if slug:
                        obj["path"] = STORY_PATH_PATTERN_V2.format(category=category, slug=slug)
            else:
                slug = str(obj.get("slug") or "").strip()
                if slug:
                    obj["path"] = STORY_PATH_PATTERN_V2.format(category=category, slug=slug)

            if path and path != obj.get("path"):
                old_path = path
            if old_path and old_path not in legacy_paths and old_path != obj.get("path"):
                legacy_paths.append(old_path)
            obj["legacy_paths"] = legacy_paths
            obj["url_schema"] = str(obj.get("url_schema") or self.url_schema or DEFAULT_URL_SCHEMA)
            obj["template_version"] = str(obj.get("template_version") or self.theme_variant or THEME_MAGAZINE_V2)

            migrated.append(obj)

        state["published"] = migrated
