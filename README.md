# Signal Atlas

Automated English trend briefing media engine for ad-funded passive income.

## Goals
- Fully automated ingest -> approve -> generate -> publish pipeline
- Google AdSense-only monetization
- Single-level categories for SEO and navigation
- Rollout ladder: `12 -> 18 -> 24` daily publish limit based on 7-day quality streak

## Category Taxonomy
- `ai`
- `tech`
- `finance`
- `healthcare`
- `stocks`
- `startup`
- `general`

## Quick Start
```bash
cd /Users/choejinseo/Desktop/github/signal-atlas
python3 run_pipeline.py --vertical all --max-publish 12 --mode production --generation-engine gemini --quality-tier premium
```

## CLI
```bash
# --vertical is ingest source selector
python3 run_pipeline.py --vertical all --max-publish 12 --mode production --generation-engine gemini --quality-tier premium
python3 run_pipeline.py --vertical finance --mode dry-run --generation-engine template --quality-tier balanced
python3 ops_report.py --window 24h --format json
python3 backfill_archive.py --scope all --generation-engine gemini --quality-tier premium
```

## Outputs
- State: `state/pipeline_state.json`
- Metrics: `state/ops_metrics.jsonl`
- Backfill checkpoint: `state/backfill_checkpoint.json`
- Content artifacts: `artifacts/YYYY-MM-DD/<category>/*.md|*.json`
- Static site: `site/category/<category>/...`

## Environment Variables
- `GEMINI_API_KEY` (required in `gemini` mode)
- `GEMINI_MODEL` (default: `gemini-2.5-pro`)
- `GENERATION_ENGINE` (`gemini` or `template`, default: `gemini`)
- `QUALITY_TIER` (`premium` or `balanced`, default: `premium`)
- `MONTHLY_BUDGET_KRW` (default: `200000`)

## Automation Rules
- Start at daily publish limit 12
- Promote when last 7 daily entries all satisfy:
  - `duplicate_rate < 5%`
  - `policy_flag_rate < 1%`
  - `indexed_rate >= 35%`
- Disable vertical when:
  - vertical `policy_flag_rate >= 3%`, or
  - vertical deploy failure streak reaches 3

## Cron Example
```bash
# Run every 3 hours in KST environment
0 */3 * * * cd /Users/choejinseo/Desktop/github/signal-atlas && /usr/bin/python3 run_pipeline.py --vertical all --mode production >> state/cron.log 2>&1
```

## GitHub Pages
- This project supports GitHub Pages deployment via `.github/workflows/pages.yml`.
- Workflow behavior:
  - Runs every 3 hours (`cron`) and on manual dispatch.
  - Builds content with `run_pipeline.py --mode production`.
  - Deploys `site/` to GitHub Pages.
- For proper page links, the workflow automatically sets `SIGNAL_ATLAS_SITE_URL` from repository info.
