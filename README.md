# Signal Atlas

Automated English trend briefing media engine for ad-funded passive income.

## Goals
- Fully automated ingest -> approve -> generate -> publish pipeline
- Google AdSense-only monetization
- 3 verticals: `ai_tech`, `finance`, `lifestyle_pop`
- Rollout ladder: `12 -> 18 -> 24` daily publish limit based on 7-day quality streak

## Quick Start
```bash
cd /Users/choejinseo/Desktop/github/signal-atlas
python3 run_pipeline.py --vertical all --max-publish 12 --mode production
```

## CLI
```bash
python3 run_pipeline.py --vertical all --max-publish 12 --mode production
python3 run_pipeline.py --vertical finance --mode dry-run
python3 ops_report.py --window 24h --format json
```

## Outputs
- State: `state/pipeline_state.json`
- Metrics: `state/ops_metrics.jsonl`
- Content artifacts: `artifacts/YYYY-MM-DD/<vertical>/*.md|*.json`
- Static site: `site/`

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
