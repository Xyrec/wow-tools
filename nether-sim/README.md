# nether-sim

Monte Carlo simulator for the "tank TBC heroics for Primal Nethers + unwanted blues,
craft and sell on the AH" gold strategy, per profession, on Thunderstrike-Horde
(Anniversary, SSC/TK phase — Primal Nether is BoP).

## Run

```
cargo run --release                # defaults
cargo run --release -- --runs 5 --share 0.35 --no-shards
```

## Model

Per day, for each of `--runs` heroics (dungeon drawn uniformly from `data/dungeons.json`,
15 pre-Magisters heroics with curated badge-boss counts):

- time = triangular(15, 35, 45) min + uniform(2, 5) min overhead (tank queue is instant)
- 1 badge per boss, +2/day for the daily quest; 10 badges auto-convert to a nether
- Primal Nether drops with `--nether-rate` (default 80%)
- each boss drops a blue (final boss: one extra + an epic); kept with `--keep-blue`
  (default ⅔) → Large Prismatic Shard, epic kept with `--keep-epic` (50%) → 1.5 Void
  Crystals (requires Enchanting; `--no-shards` disables)
- flat +25g loot/vendor income, −6g repairs per run

Nethers are spent greedily by profit-per-nether into that profession's AH-sellable
crafts (from Zygor's recipe DB priced with the TSM app snapshot: sell = Horde
marketValue × 0.95, mats = Horde MV → Alliance MV → region MV → vendor). Daily
demand per item ~ Poisson(`--share` × region sold/day); crafting stops at
`--headroom` × daily demand of inventory per item (ceil, so slow epics may keep one
listed). Unsold terminal inventory recovers mat cost only; leftover nethers/badges
expire worthless (conservative).

## Inputs

- `~/ccsandbox/wow/primal-nether-analysis/output/nether_recipes.json`
  (regenerate via `lua extract_recipes.lua` there when recipes change)
- TSM AppHelper `AppData.lua` + TSM `VendorSell.lua` from the game AddOns folder
  (refresh by letting TSMApplication sync)
- `data/dungeons.json` — curated boss counts (cross-checked against AtlasLoot)

## Known simplifications

- Prices are a static snapshot; your own 4–6 nethers/day of supply will move thin
  markets. Recipe ownership is assumed complete per profession (no pattern
  acquisition costs/rep gates). Deposit fees, cancel-scans, and AH time ignored.
- `--share` (default 25%) is a guess at Thunderstrike-Horde's slice of the Fresh-EU
  region (Thunderstrike + Spineshatter; Soulseeker is HC-only).
