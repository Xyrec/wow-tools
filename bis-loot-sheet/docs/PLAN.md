# TBC Item Distribution — Project State & Plan

Living document. **The "Current state" section is authoritative**; the decision
history at the bottom explains how we got here. Last full rewrite: 2026-08-18.

## What this is

An **item distribution site** for the guild (Fel Good Inc.), built from real
Warcraft Logs gear data of the 2021–22 TBC Classic run: for each spec and each
Anniversary phase, what the top ~2,000 ranked players (US+EU) actually wore,
per slot, with usage percentages. Higher % ⇒ more likely *the* BiS. It exists to
replace untraceable hand-made BiS sourcing for the guild's loot prio sheets
(origin story: `../ORIGINAL_CONVO.txt` — the unique-equip Rod of the Sun King
mistake).

**Live site:** https://bis-loot-sheet.itsgonnabealongnight.workers.dev
(Cloudflare Workers static assets; **every push to `main` redeploys** via
Workers Builds — project path `bis-loot-sheet/app`, build `npm run build`,
deploy `npx wrangler deploy`, config `app/wrangler.jsonc`.)

## Current state (2026-08-18)

### Canonical dataset — COMPLETE, all 5 phases

- **Top-2000 region windows only** (Xyrec's standing decision): per phase, per
  spec, per boss — WCL region-level ranking pages 1–20 for US and EU, phase-pure
  partition, **no per-server data, no KR/TW/CN** (explored, then deliberately
  deleted: too granular, admits weak logs; and the cross-validation below showed
  the window ≈ elite band anyway).
- Datasets are keyed by **Anniversary phase, not WCL zone** (`phase-1`…`phase-5`;
  phase-1 pools the two WCL zones Kara + Gruul/Mag — see `PHASES` in `config.py`).
- ~4.2M phase-pure parse records across 49 bosses; raw cache ~6.9 GB in
  `data/raw/` (gitignored), one JSON file per WCL API page, fully resumable.
- Each record = one player's best kill of one boss on one spec, incl. 18-slot
  gear snapshot. **Row-level phase purity**: any row wearing ANY later-phase
  raid drop is dropped at aggregation (poison set = later phases' lootmaps).
  P3 drops 35.7% of its partition rows this way; phases whose partitions predate
  the next tier drop 0% (a good consistency check).

### Pipeline (Python 3.14, uv, ruff — `src/bis_pipeline/`)

```
uv run bis-pipeline status                   # API points budget
uv run bis-pipeline discover                 # cache spec/encounter/server metadata
uv run bis-pipeline fetch <zone> --max-pages 20 --region-only   # canonical fetch
uv run bis-pipeline aggregate <phase|zone> --max-pages 20       # raw -> distributions
uv run bis-pipeline enrich <phase|zone>                         # + cmangos facts, app sync
```

- `client.py` — OAuth client-credentials (token cached ~1yr, creds in `../.env`,
  gitignored: `WCL_CLIENT_ID`/`WCL_CLIENT_SECRET`); every query piggybacks
  `rateLimitData`; sleeps to hourly reset when <20 of 3,600 points remain;
  429/5xx backoff; 2-min budget heartbeat in logs.
- `fetcher.py` — page cache with `_done` depth markers (never downgraded),
  corrupt-page self-healing, `--region-only` = no probe & no server descent
  (the canonical mode). Legacy full-depth/server-descent code paths still exist
  but are exploration-only on explicit request.
- `aggregate.py` — pools a PHASE's zones; two-pass percentile banding
  (`top10`/`mid50`/`all`) plus the source-based `top2000` band; per-encounter
  kill-duration histograms (15s bins) for the overview; floors pct≥0.5 & count≥5.
- `enrich.py` — joins cmangos 2.4.3 sqlite (`../../sources/cmangos-tbc-db/`):
  quality, ilvl, inventory slot, armor type, unique/unique-equipped, set id,
  tier-token detection (class 15 q4), PvP flag (resilience stat 35 OR
  gladiator/marshal/etc. name), allowable classes; merges the phase's lootmaps
  (boss → droppable items, incl. drop-only tier tokens with WCL-fetched icons);
  `laterPhase` marks items from future phases. **Phase purity is three-layered
  (2026-08-18):** (1) raid lootmaps, (2) wowhead per-item phase tags
  (`item_phases.py`, tooltip endpoint dataEnv=5, cache `meta/item_phases.json`,
  refresh `bis-pipeline item-phases`) catching non-raid additions like 2.3
  badge gear (the Carved Witch Doctor's Stick case), (3) **empirical clearance**
  (`meta/item_clearance.json`): items worn >=20x in the P1/P2 partitions —
  which verifiably predate the next tier — are cleared down to that phase,
  because wowhead tags are sometimes wrong vs classic reality (Band of
  Eternity: tagged P3, demonstrably worn Dec 2021). Effective phase =
  min(tag, clearance). Writes full multi-band JSON to
  `data/enriched/` AND a **diet app copy** to `app/src/data/{phase}.json`
  (top2000 band only, flattened — the app has NO band concept — items pruned to
  referenced ones; ~480 KB/phase).
- `lootmap.py` — encounter→loot via creature name-match + `CREATURE_OVERRIDES`
  for fights whose loot rides on a differently-named body: Reliquary→Essence of
  Anger, Illidari Council→Zerevor+Gathios, ZA "Daakara"→Zul'jin, Kalecgos→
  Sathrovarr, Eredar Twins→Sacrolash+Alythess, M'uru→Entropius. **When adding a
  zone, verify every boss appears in the lootmap** (missing ones under-fill the
  poison set for earlier phases).
- Known data quirks: WCL lists US server `maladath` twice (deduped in
  discovery); WCL gear arrays put two-handers in the main-hand index (split at
  display time); some "Main Hand" tooltips (Dragonstrike, The Decapitator) are
  genuinely One-Hand in final-patch data — dual-wielding them is real; one
  Anniversary-era item id (185988) polluted a classic partition (dropped, with
  warning, by enrich).

### Web app (`app/` — Vite 8, React 19, Tailwind 4, shadcn/Base UI)

- Title: **"TBC Item Distribution — from Warcraft Logs"** ("BiS" only in the URL).
- Phase picker: Select (top right), defaults to latest phase present; per-phase
  **lazy chunks** via non-eager `import.meta.glob` + `useZone` hook (main bundle
  ~220 KB gzip; each phase ~70 KB gzip, immutably cached by hash across deploys).
- Overview (default view): stat tiles (parses analyzed, data updated) +
  kill-time histogram per boss (15s bins, 99.5% tail trim, dataviz-validated
  amber #d97706); boss Select grouped by raid with labels + separators
  (`raidOfEncounter` in `lib/wow.ts` maps encounter-id ranges to raid names).
- Spec pages: slot cards with item icons, quality colors, usage bars; BiS
  highlight = top item + anything within 5pp (rings/trinkets highlight top TWO
  + ties, since two are worn); badges: Set/Token (emerald), PvP (red text),
  Unique/Unique-Equipped (amber, only on ring/trinket/weapon slots), red
  "P4 item" laterPhase badge kept as a **canary** — post-filter it should never
  render; if seen, a non-raid contamination path exists (vendor/badge gear, PvP
  season timing — those aren't in raid lootmaps).
- Wowhead tooltips via their official `tooltips.js` (links are wowhead item
  URLs; SPA re-scans after renders). Tank/healer pages carry metric caveats.
- Selects follow canonical Base UI shape: `items` prop + childless
  `<SelectValue/>`, groups, separators between labeled groups,
  `alignItemWithTrigger=false` default in `ui/select.tsx`.
- No arbitrary Tailwind values in our code (vendored `ui/` excepted).

### Validation (2026-08-17, scripts/compare_wowtbc.py)

Against freshly-scraped wowtbc.gg lists (parent repo `cargo run -- scrape`;
their phase keys: phase-0=Pre-Raid, 1=T4, 2=T5, 3=T6, 4=ZA, 5=SWP):
strict = their BiS within our co-BiS set; loose = within our top 3.

| band | T6 vs our P3 | T5 vs our P2 |
|---|---|---|
| top10 | 69.0 / 88.5 | 79.5 / 95.2 |
| top2000 | 60.5 / 82.6 | 70.6 / 92.7 |
| mid50 | 50.8 / 76.2 | 69.6 / 89.4 |
| all | 51.4 / 77.7 | 73.2 / 94.2 |

Top-10% matches curated lists best; **Xyrec still chose top2000 as the only
exposed dataset** (uniform definition, cheap, keeps weak logs out) — respect
that; the multi-band data remains in `data/enriched/` if the question reopens.
Largest curated-vs-logs disagreements: Marksmanship, Holy Paladin/Priest.
P4≈P3 similarity is genuine history (85% identical top items; the diffs are
the famous ZA pieces — Amani Longbow, Brooch of Nature's Mercy, etc.).

### Scripts (`scripts/`)

- `compare_wowtbc.py <phase-tag> <wowtbc-phase-key>` — the validation above.
- `audit_raw.py [zone-tag ...]` — verifies every (boss, spec, region) slice is
  complete (contiguous pages, exhausted-or-20). Run after any fetch.

## NEXT UP — Mechanism 2: the loot prio sheet (not started)

The officer-facing deliverable. All ingredients exist in the app data:
1. **Roster builder** (TS, in-app): pick tanks/healers/DPS + specs (maybe
   professions); stored client-side.
2. **Prio-chain generation** (TS, client-side, no backend): per droppable item
   (incl. tier tokens via lootmap/sources), order specs by *relative* usage
   (99% vs 68% ⇒ 99% first), `=` within an epsilon, `MS > OS` tail; only
   rostered specs; unique-equip conflicts surfaced (the Rod/Talon failure mode);
   cross-phase persistence (item still worn in later phases ⇒ boost) is
   derivable from the per-phase JSONs.
3. **Export** CSV/JSON in the officers' sheet shape (`../old-data/*.csv`:
   per-boss sections, `Item, Spec > Spec = Spec > MS > OS`).
4. QA loop with Xyrec → officers. Nothing handed over until correct.
Needs from Xyrec: the guild roster when starting.

## Decision history (condensed — details in git log)

- 2026-08-15: /grill-me interview → two mechanisms; Python pipeline + TS app
  split; phase-pure partitions. First fetch + first QA validated the thesis
  (dual Netherbane, Talon+Rod exactly as the Discord argument predicted).
- 2026-08-16: partition rule corrected — a raid's *earliest* partition is
  progression-only (P3 partition = Jan–Feb 2022, everyone in P2 gear); phase
  BiS = **latest partition before the NEXT tier**: Kara/Gruul-Mag→p1, SSC/TK→p3
  (P2.5), BT/Hyjal & ZA→p5 ("P3.5 & P4"), Sunwell→p6. Row-level poison purge
  replaces item flagging. (PC crash mid-fetch → corrupt-page self-healing.)
- 2026-08-16/17: explored full per-server population fetching (US/EU descents,
  ~16 GB); built percentile bands from it; cross-validated vs wowtbc.gg; then
  **deleted all non-top-2000 data** — canonical dataset = region windows only.
  Bands removed from the app; band toggle removed; top2000 is the app.
- 2026-08-17: deployed to Cloudflare Workers (push-to-deploy); bundle diet +
  lazy chunks; datasets re-keyed by phase (P1 merges Kara+Gruul+Mag); all five
  phases shipped one at a time; ZA/Sunwell lootmap overrides fixed (their
  absence had under-filled the poison set — P3 purge went 23.3%→35.7%).

## Reference

- `../ORIGINAL_CONVO.txt` — Discord conversation that started this.
- `../old-data/*.csv` — the officers' existing sheet format (prio-chain target).
- WCL API: https://www.warcraftlogs.com/v2-api-docs/warcraft/ — GraphQL,
  self-describing via introspection. Rankings page cap: 20 pages per filter
  combination. Classic endpoint: https://classic.warcraftlogs.com/api/v2/client.
- Classic 2021 zones (frozen, 7 partitions [1:P1 2:P2 3:P2.5 4:P3 5:"P3.5&P4"
  6:P5 7:Pre-Patch]): Kara 1007, Gruul/Mag 1008, SSC/TK 1010, BT/Hyjal 1011,
  ZA 1012, Sunwell 1013. Non-frozen 1047/1048/1056/1060 mirror the Anniversary
  run (potential future comparison).
- Parent repo: wowtbc.gg scraper (`cargo run -- scrape` → `output/*/
  wtbc_bis_gear.json`), cmangos TBC sqlite.
