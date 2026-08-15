# BiS Loot Sheet — Project Plan

Living document. Captures decisions from the planning interview (2026-08-15) so work
survives context compaction. Update as decisions land.

## Background / Motivation

Guild (Fel Good Inc.) loot prio sheets are hand-made by officers cross-referencing
BiS lists from memory; sourcing is untraceable and public lists (Wowhead, Icy Veins,
wowtbc.gg, AtlasLoot) disagree and borrow from each other. Concrete failure found:
Phase 2 sheet lists unique-equip Rod of the Sun King as the *only* enhancement shaman
weapon (roster-tailored to one blacksmith), missing Talon of Azshara/fist prio.
Full Discord context: `../ORIGINAL_CONVO.txt`.

Thesis: **logs don't lie.** The 2021–2022 TBC Classic run's data still exists on
classic.warcraftlogs.com — derive BiS empirically from what top players actually wore.

Current guild run: TBC Anniversary (fresh.warcraftlogs.com), currently late Phase 2,
Phase 3 (Hyjal/BT) sheet is the near-term deliverable, but project covers **all phases**.

## Architecture: two mechanisms

### Mechanism 1 — the BiS list (build first)

1. **Scrape/parse**: query classic.warcraftlogs.com (v2 GraphQL API) for gear worn by
   ranked players, per spec per boss, and aggregate into per-slot item usage
   distributions.
2. **Site**: Vite + shadcn web app showcasing the BiS list. Look-and-feel inspiration:
   wowtbc.gg BiS pages.
3. **QA**: app shows the % distribution of each item per slot — highest % is *the*
   BiS item; anything **< 2% usage is noise and ignored**.

### Mechanism 2 — the loot prio sheet/data (build second, on top of 1)

1. Figure out the guild roster (class/spec combinations we run).
2. Adjust the BiS data to suit that roster.
3. QA/validate — Xyrec previews to officer/GM team; nothing is handed over until
   correct.
4. Iterate. Key weighting rule: cross-spec priority comes from *relative* usage —
   e.g. a trinket used by 99% of spec A but 68% of spec B → spec A gets higher prio.

**Roster-builder idea (adopted direction):** the site lets you *create* a roster —
select main/off tanks, healers, DPS, each with spec (and maybe professions) — and
generates the loot prio list from the BiS data + roster. So the data core stays
roster-agnostic; roster tailoring is a parameterized app feature, not baked into data.

## Decisions so far

| Decision | Choice |
|---|---|
| Deliverables | Web app (latest Vite + shadcn) + JSON/CSV export importable into Google Sheets. All phases, not just Phase 3. |
| Phase purity | classic WCL has per-phase **partitions**: P1, P2, P2.5, P3, "P3.5 & P4", P5, Pre-Patch (ignore Pre-Patch — WotLK class changes). For each raid, use the **earliest partition** in which that raid existed; later partitions poison data with unreleased gear. Verify exact raid→partition mapping against the site/API. |
| Anniversary mapping | fresh.warcraftlogs: Phase 1 = Kara/Gruul/Mag, Phase 2 = SSC/TK, Phase 3 = Hyjal+BT (upcoming). No later phases exist there yet. |
| Sample cut | **Two-band comparison**: top ~10% AND a mid-band (~25th–75th percentile) per spec per boss. Primary BiS from top band; mid-band exposes elite-vs-population divergence (answers officers' "speed-parse skew" objection). |
| Role metrics | All roles by their default WCL parse metric (dps/hps), one uniform pipeline. Tank & healer lists carry a visible caveat: "assumes maximizing tank DPS / HPS". Officers apply judgment — this is a first draft. |
| Noise floor | Items under 2% usage within a spec's band are ignored. |
| Pipeline tech | **Python 3.14** project in `bis-loot-sheet/` (init with `uv`, lint with `ruff`): WCL scraping, aggregation, cmangos sqlite enrichment (stdlib `sqlite3`) → static JSON. |
| Prio logic | **TypeScript, in the app.** Python produces facts (distributions + item metadata: unique-equip, class restrictions, token mappings baked into JSON); TS applies policy — roster builder computes prio chains client-side and exports CSV/JSON for Google Sheets. No backend. |
| Hosting | Cloudflare Pages eventually; **local dev only for now** — deployment is a very-late-stage concern. Fully static build. |
| Tier tokens | Static token→{class: item} mapping (~15 tokens T4–T6, cross-checked against cmangos DB). BiS view shows pieces (what logs contain); prio sheet shows the token with its chain derived from each redeeming spec's usage% of their piece. **Never assume 4pc is best** — some set bonuses are bad (e.g. T5 resto shaman 4pc); usage data decides. |
| Gems/enchants | Pipeline **stores raw gear snapshots** (gems/enchants included, no re-scrape needed later); aggregation + app v1 are **items-only**. Gem/enchant views are a later feature. |

## Also in scope (settled, no interview needed)

- **Cross-phase persistence**: since all phases are collected, flag items that stay
  equipped in later phases' data ("repeated items per phase" → higher prio).
- **Unique-equip awareness**: from cmangos DB; the Rod/Talon failure mode must be
  visible in prio output (e.g. warn when a spec's only listed weapon is unique).
- Spec taxonomy: WCL's spec names as-is (all specs that appear in rankings).

## API exploration findings (2026-08-15, verified live)

- Auth works: client-credentials against `https://www.warcraftlogs.com/oauth/token`,
  token valid ~1 year. Credentials in `../.env` (gitignored). Classic endpoint:
  `https://classic.warcraftlogs.com/api/v2/client`.
- **Gear comes inline with rankings**: `Encounter.characterRankings(partition, className,
  specName, metric, page, includeCombatantInfo: true)` returns per-character `gear`
  (18 slots, `{id, name, quality, icon}`) plus name, amount, duration, startTime,
  faction, talents, report code. No per-report combatantInfo fetches needed.
- **No gems/enchants in rankings gear** — only id/name/quality/icon. Gem/enchant data
  would require per-report fetches; deferred indefinitely (amends earlier decision:
  nothing to "store for later" from this endpoint beyond what we aggregate).
- **Pagination: 100/page, hard cap at page 20 — but PER FILTER COMBINATION.** Each
  distinct combination of (encounter, partition, metric, serverRegion, serverSlug,
  className, specName, …) gets its own 2,000-row window. Verified live: region slicing
  (EU/US return distinct rankings), serverSlug slicing (firemaw works), and omitting
  className returns all classes with each row labeled `class`/`spec` (bucket
  client-side). Regions: US 53 servers, EU 54, KR 8, TW 11, CN 113.
- **Fetcher design — region-first, per-spec, adaptive server descent** (Xyrec
  directives: get ALL the data, never a subset of the top; ALWAYS filter by spec —
  the BiS list is spec-based and other specs must not poison the data):
  1. Per (zone, encounter, earliest partition, metric, region, class+spec): fetch
     pages 1–20 while `hasMorePages`, `includeCombatantInfo: true`. 5 regions
     (US/EU/KR/TW/CN) × 2,000 cap per spec per boss ≈ up to 10k/spec/boss. Context:
     even the GLOBAL top-2000 for the most-played spec (Arcane on Kael'thas) reaches
     the 91st percentile, so region slicing comfortably covers the top 10%.
  2. If a (region, spec, boss) slice saturates (page 20 AND `hasMorePages`),
     re-fetch that combo at server granularity within the region and **replace** the
     region slice with the server slices (not union — ranking rows carry no `server`
     field, so cross-slice character dedup is unreliable; replacement sidesteps it).
     Blanket per-server fetching was rejected: ~287k mostly-empty probe queries.
     **Probe-first optimization**: for US/EU, fetch page 20 FIRST — if it's full and
     `hasMorePages`, mark saturated and descend immediately, skipping 19 region pages
     that replacement would discard anyway. First live run showed saturation is
     common for popular specs in US/EU (Balance/US saturated on the first spec
     tried), so this saves on the order of a day of API budget across the scrape.
  3. Rate-limited token bucket targeting ~3,400 of the 3,600 points/hour, backoff on
     429s; every raw response cached to disk keyed by full query params; fully
     resumable; aggregation is a separate offline step over the cache.
  4. Fetch order: BT/Hyjal (P3 — near-term deliverable) first, then remaining raids.
- Kill durations: not used for filtering now. Every row carries `duration`, so once
  data is in we can plot the kill-time bell curve and compare the guild's own kill
  times against the top-20-pages-per-spec distribution.
- **Consequence: true percentile bands are back.** With the full population fetched
  per spec/boss, the original decision stands exactly as made: top 10% band and
  25th–75th mid-band computed from real population counts. Kill-time bell curves also
  computable (every row carries `duration`). The earlier "rank-based bands" amendment
  is void.
- Rate limit: 3,600 points/hour (~2–3 points per 100-row page with combatant info).
  Points spent scale with rows actually retrieved, so adaptive slicing wastes almost
  nothing on empty slices. Whole-history scrape may take days of budget; caching
  makes it incremental and restartable — exact populations are discovered as we go.

### Classic (2021 run) zone/partition map — verified via API

Expansion "The Burning Crusade" id 1001. The 2021-run zones are the frozen ones with
7 partitions [1:P1, 2:P2, 3:P2.5, 4:P3, 5:"P3.5 & P4", 6:P5, 7:Pre-Patch].
**Earliest partition per raid** (confirmed by site defaults):

| Raid | Zone id | Earliest partition | Anniversary phase it informs |
|---|---|---|---|
| Karazhan | 1007 | 1 (P1) | Phase 1 |
| Gruul / Magtheridon | 1008 | 1 (P1) | Phase 1 |
| SSC / TK | 1010 | 2 (P2) | Phase 2 |
| BT / Hyjal | 1011 | 4 (P3) | Phase 3 ← near-term goal |
| Zul'Aman | 1012 | 5 (P3.5 & P4) | Phase 4 |
| Sunwell Plateau | 1013 | 6 (P5) | Phase 5 |

SSC/TK encounter ids: Hydross 623, Lurker 624, Leotheras 625, Karathress 626,
Morogrim 627, Vashj 628, Al'ar 730, Void Reaver 731, Solarian 732, Kael'thas 733.

Non-frozen zones 1047/1048/1056/1060 (partitions P1/P2/P3) appear to be the current
Anniversary zones mirrored on the classic endpoint — potentially useful later to
compare the current run against the 2021 run.

Early sanity check: #1 Enhancement parse on Kael'thas (P2 partition) wears **dual
Netherbane** — phase-pure data immediately contradicts the officers' Rod-only sheet.

## Open implementation questions

- Confirm amended rank-based banding with Xyrec (see above).
- Prio chain synthesis defaults: `=` when usage within some epsilon, `>` otherwise,
  `MS > OS` tail always appended. Tune during Mechanism-2 QA with officers' feedback.
- Faction-specific drops, if any, per raid (rankings include `faction`, so testable).
- Spec list per class as WCL names them (query `gameData` or observe from rankings).

## Build status (2026-08-15)

- Python package `bis-pipeline` scaffolded in `bis-loot-sheet/` (uv, Python 3.14,
  httpx runtime dep, ruff dev dep; `uv run ruff check` clean).
- Modules: `config.py` (zone/partition map, healer-spec metric mapping, TBC class
  exclusions — classic gameData includes DK/Monk which don't exist in TBC),
  `client.py` (OAuth client-credentials with token cache; every query piggybacks
  rateLimitData; sleeps until window reset when <20 points remain; 429/5xx backoff),
  `discovery.py` (cached spec list / encounters / servers under `data/meta/`),
  `fetcher.py` (slicing engine as designed above), `cli.py`
  (`uv run bis-pipeline status|discover|fetch <zone> [--encounter ID]`).
- Discovery cached: 28 TBC class/spec pairs; encounters — kara 10, gruul-mag 3,
  ssc-tk 10, bt-hyjal 14 (Naj'entus 601 … Illidan 609, Winterchill 618 … Archimonde
  622), zul-aman 6, sunwell 6; servers US 53 / EU 54 / KR 8 / TW 11 / CN 113.
- Estimate run in progress: Naj'entus (601), all specs × regions, to measure real
  points cost per boss before unleashing the full scrape.

## Needs from Xyrec

- WCL API client credentials (create at https://classic.warcraftlogs.com/api/clients),
  for the v2 GraphQL API (client-credentials flow works for public data).
- Headed agent-browser login to classic.warcraftlogs.com when browsing old TBC
  content on the website itself (Classic is currently in MoP; old data needs login).
- The guild roster (class/spec/professions) when Mechanism 2 starts.

## Reference material

- `../ORIGINAL_CONVO.txt` — Discord conversation that started this.
- `../old-data/Fel Good Inc. Loot Prio - Phase 2 {SSC,TK}.csv` — existing officer
  sheet format. Structure: per-boss sections, rows = `Item Name, Bias chain…` where
  chains look like `Survival > Enhancement > MS > OS`, `Resto = Holy > MS > OS`,
  including conditionals ("Feral tank until expertise cap", "Mage until 2p T5") and
  specials (Disenchant, PvP item = open for any, BiS > Non BiS for tokens).
  Tanks/healers are first-class in these chains (~⅓ of named-spec lines).
- WCL API docs: https://www.warcraftlogs.com/v2-api-docs/warcraft/ and
  https://www.warcraftlogs.com/api/docs
- wow-tools (parent repo): scraped BiS lists (wowtbc.gg etc.) for cross-validation;
  cmangos TBC sqlite DB (`sources/cmangos-tbc-db/tbcmangos.sqlite`) for item stats,
  unique-equip flags, allowable classes.
