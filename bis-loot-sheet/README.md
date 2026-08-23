# TBC Item Distribution (bis-loot-sheet)

Item distribution site + data pipeline: what the top ~2,000 ranked players per
spec actually wore in each TBC Anniversary phase, from Warcraft Logs data of the
2021–22 TBC Classic run.

**Read `docs/PLAN.md` first** - it is the authoritative current-state document.

Live: https://bis-loot-sheet.itsgonnabealongnight.workers.dev
(auto-deploys on push to `main` via Cloudflare Workers Builds)

## Quickstart

```bash
# Pipeline (Python 3.14, uv). Needs ./.env with:
#   WCL_CLIENT_ID=…  WCL_CLIENT_SECRET=…   (create at warcraftlogs.com/api/clients)
uv sync
uv run bis-pipeline status                                    # API budget check
uv run bis-pipeline fetch bt-hyjal --max-pages 20 --region-only  # canonical fetch mode
uv run bis-pipeline aggregate phase-3 --max-pages 20
uv run bis-pipeline enrich phase-3        # -> data/enriched/ + app/src/data/

# Verify raw data completeness after fetching
uv run python scripts/audit_raw.py

# Web app (Vite + React + shadcn)
cd app && npm install && npm run dev

# Validation vs wowtbc.gg (scrape first: cd .. && cargo run -- scrape)
uv run python scripts/compare_wowtbc.py phase-3 phase-3   # our phase, their key (3=T6)
```

Datasets are keyed by Anniversary phase (`phase-1`…`phase-5`); phase-1 pools
Karazhan + Gruul/Magtheridon. Raw cache in `data/raw/` (gitignored, resumable);
the app consumes only the diet copies in `app/src/data/`.
