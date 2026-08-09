# Account Profession Plan — Gold Engine

*Drafted 2026-07-30, revised 2026-08-09. Thunderstrike (Anniversary TBC, SSC/TK phase, content drop imminent).*
*Prices from the TSM app snapshot of 2026-08-09; re-run the tooling (below) after major market moves.*

> **2026-08-09 revisions**
> 1. **Badges cannot buy Primal Nethers this phase** (G'eras doesn't stock them yet) — heroic
>    drops are the only source. Nether supply at 3 runs/day: ~2.4/day, not ~3.6/day.
>    `nether-sim` now defaults `--badges-per-nether 0`; pass `10` to model the later-phase vendor.
> 2. **Adamantite Bar crashed to ~1g36** (24 auctions, 250/day region — a real move, not a bad tick),
>    gutting mat costs on BS armor. Combined with scarcer nethers (scarcity favours margin over
>    velocity), **Blacksmithing now leads the sim at 1–4 runs/day**; LW only overtakes at 5.
>    This *reinforces* keeping BS on the paladin. Re-check monthly: if adamantite recovers,
>    LW's flatter curve reasserts.
> 3. Faction check: TSM has both Thunderstrike factions and the tooling defaults to **Horde**.
>    Alliance values run ~5–10% lower (Nethercobra 113g vs 124g; Runic and shards near-identical),
>    so conclusions hold either way — but flip the default in the scripts if playing Alliance.

## Goal

Convert a mostly-parked roster into a semi-afk gold engine around three pillars:

1. **Tanking heroics** on the paladin → Primal Nethers (BoP, ~80% per run, drops only)
   + BoP blues (→ shards) + badges (gear/gems only this phase).
2. **Transmute Master cooldowns** on every parked alchemist (Skyfire Diamond, ~15.5% proc,
   ~20–30% extra yield → ~46–58g/day per character with near-free uncut gems).
3. **Passive AH postings** (bags, threads, bracers) via TSM, 1–2 posts/day.

Target steady state: **~780–860g/day ≈ 23–26k g/month** at 3 heroics/day
(15–17k at 1 run/day, 30k+ at 5).

## Roster: final state

| Character | Class | Lvl | Professions (final) | Change | Investment |
|---|---|---|---|---|---|
| Yrsadriel (main) | Shaman | 70 | Alchemy 350+ **TM** + Jewelcrafting | none (recipe owned, keep TM; EM pivot is a phase-launch decision) | 0g |
| Xyrec | Mage | 70 | Tailoring + Enchanting | none | 0g |
| Xyrekk (tank) | Paladin | 70 | Blacksmithing + **Enchanting** | 2nd slot → Enchanting; buy BS plans | ~1,190g plans + ~800–1,200g enchanting |
| Xycaelis | Druid | 70 | **Alchemy TM** + **Herbalism** | Alchemy 350 + TM + recipe; Herbalism (flight-form gathering feeds the alchemy fleet) | ~600g |
| Hektorion | Warrior | 58 | **Alchemy TM** + **Leatherworking** | Alchemy 350 + recipe now, TM at 68; LW for leg armors + drums | ~200g now + ~400g at 68 + ~3,080g LW |
| Hunter (restore) | Hunter | ~63 | **Alchemy TM** + LW *(optional)* | Alchemy 350 + recipe now, TM at 68. LW **not prioritised** — may stay parked, or take a gathering profession if a farm becomes relevant (pet tanking makes hunters strong farmers) | ~200g now + ~400g at 68 (+ paid restore) |
| **Total** | | | | | **~3,000–3,400g now, ~800g deferred, +~3,080g if/when LW** |

Payback of the full outlay: **~4–5 days** of the running engine, or ~1 week of tanking alone.

### Why these choices (one line each)

- **Nethers/badges/heroic blues are all BoP** → they only monetize through the *paladin's own* professions. His two slots are the scarcest resource on the account: nether sink (BS) + BoP-blue disenchanting (Enchanting). Alchemy never goes here.
- **BS stays over LW**: as of 2026-08-09 the sim scores BS **ahead** at 1–4 runs/day
  (629g vs 585g at 3 runs) on cheap adamantite + drops-only nether supply; LW leads only at
  5 runs (943g vs 854g). Releveling LW costs ~3,080g to chase a lead that only exists at max
  activity. Revisit if adamantite recovers or nether output permanently outgrows what BS's
  ~4–6 sales/week can absorb (LW takes everything at ~115g/nether; nethers bank fine meanwhile).
- **Mage unchanged**: tailoring is sunk and passively earns (bags, Mystic Spellthread @ Scryers Honored, cloth CD); her enchanting DEs world-farm BoEs. Alchemy is fungible — parked alts take it.
- **TM stays on Yrsadriel through the lull**; Elixir Master is the *active* pivot at content launch (flasks are currently below-cost without a spec; EM is the entire margin — see "Phase-launch playbook").
- **Warrior takes LW, not Engineering**: a nether-earning character needs a *repeatable sellable*
  outlet. Engineering has 23 nether recipes but 22 are BoP goggles (5 nethers total, one-time);
  only the Gyro-Balanced Khorium Destroyer is BoE, at 0.22 sold/day. LW converts every nether at
  ~115g and additionally gives him **drums for his own tanking**.
- **Hunter's LW is optional** — he only needs a nether outlet if he actually runs heroics.
  Parked, Alchemy alone is the whole point of the character.
- **Druid takes Herbalism** — she's the parked AH character, won't run heroics (so no nethers
  wasted), and flight-form gathering is fast.

## Verified game rules (cmangos TBC 2.4.3 DB, checked 2026-08-09)

Local DB now at `sources/cmangos-tbc-db/tbcmangos.sqlite` (285 MB, gitignored; from
github.com/cmangos/tbc-db releases → `tbc-sqlite-db.zip`, plus `src/SpellAuraDefines.h`
from the mangos-tbc repo). Query it for item bind type, `RequiredSkill`, and rep gates
instead of guessing.

| Question | Answer |
|---|---|
| Drums usable by non-leatherworkers? | **No** — Drums of Battle `RequiredSkill 165 (LW) rank 350`. Whole line is LW-gated. |
| Bombs/grenades sellable to rogues etc.? | **No** — every bomb/sapper/grenade is `RequiredSkill 202 (Eng)`. Engineer-to-engineer trade only. |
| Engineering goggles | All BoP, `RequiredSkill 202`. ilvl 127 = 1 nether; ilvl 159 = 4 nethers + the 127 goggle. |
| BS bracer/glove socketing | **Does not exist in TBC** (zero "Socket" spells) — that's WotLK. |
| Ring enchants | Enchanter-only: Striking/Spellpower (360), Healing Power (370), Stats (375). |
| Leg armors / spellthreads | `RequiredSkill 0` — anyone can use them. That's why the markets are deep. |
| Scopes / ammo / potion injectors | `RequiredSkill 0` — Engineering's only genuinely open markets. |

### Leg enhancement reps and stats

**Leatherworking has no Aldor/Scryers-style fork** — Honor Hold (946) and Thrallmar (947) are
just the Alliance/Horde mirrors of the same pattern, and Cenarion Expedition (942) is neutral.
A leatherworker gets **both** leg armors. Only Tailoring's spellthreads are mutually exclusive.

| Enchant | Stats | Faction | Standing |
|---|---|---|---|
| Nethercobra Leg Armor | +50 AP, +12 melee crit | Honor Hold / Thrallmar | Exalted |
| Cobrahide Leg Armor | +40 AP, +10 melee crit | Honor Hold / Thrallmar | **Honored** |
| Nethercleft Leg Armor | +40 Sta, +12 Agi | Cenarion Expedition | Exalted |
| Clefthide Leg Armor | +30 Sta, +10 Agi | Cenarion Expedition | **Honored** |
| Runic Spellthread | +20 Sta, +35 Heal, +35 SpDmg | The Scryers | Exalted |
| Golden Spellthread | +20 Sta, +66 Heal, +22 SpDmg | The Aldor | Exalted |

The Honored-tier rares need **no Primal Nether** and sell 14–17/day region — an LW alt earns
during the rep grind, long before Exalted.

## Tailoring cloth cooldown (mage)

Specialization doubles the output of your chosen cloth, which flips it from a loss to a real
earner. Run it whenever it's up:

| Cloth | Unspecialized | Specialized (×2) |
|---|---|---|
| Shadowcloth | −5g | **+45g** |
| Primal Mooncloth | −4g | **+36g** |
| Spellcloth | −9g | **+31g** |

*Unverified:* the cooldown length in TBC (daily vs 4-day) — check the tooltip; it scales this
from ~31–45g/day down to ~8–11g/day.

## Step-by-step (lowest-hanging fruit first)

Order principle: cheap unlocks that earn immediately come first; anything requiring
character levels comes last (those alts craft daily while they level anyway).

**1. Yrsadriel — already done (0g, today).**
Keep clicking the Skyfire CD (20h — click on login, don't schedule life around it).
Route gems through her own Chaotic Skyfire cut when the cut market isn't crowded (+~13g),
sell uncut otherwise. ~60–70g/day.

**2. Xyrekk — buy BS plans and start tanking (day 1, ~1,190g).**
- AH plans, immediate payback (1–2 crafts each): *Bracers of the Green Fortress* (~387g),
  *Black Felsteel Bracers* (~476g), *Blessed Bracers* (~150g).
- Commission plans, dirt cheap: *Runic Hammer* (~50g), *Felsteel Reaper* (~83g),
  *Felsteel Longblade* (~48g) — advertise "my nether, your gold" in trade.
- Tank 1–5 heroics/day. Nethers → bracers (~300g each, market absorbs ~4–6/wk);
  surplus nethers **bank** (they don't expire; phase 3 wants them). Badges buy gear/gems
  only this phase — no nethers from G'eras yet.
- Rep from tanking unlocks the vendor plans — Wildguard (CE exalted), Iceguard (Thrallmar) —
  and with adamantite at ~1g36 those are now the **top earners on the account**
  (~475–630g profit per craft). Prioritise that rep.

**3. Xyrekk — Enchanting in the 2nd slot (week 1, ~800–1,200g cash).**
Level it off run loot + cheap AH mats to ~325 (enough to DE heroic blues → Large
Prismatic Shard ~21g each, ⅔ of blues kept ≈ +40–65g/run). This is a third of the
tanking income — do not skip. Finish to 375 whenever convenient.

**4. Xycaelis (70, parked) — full transmute alt (~600g, one afternoon).**
Alchemy 1→350 (~197g mats; near-free if leveling potions are TSM-posted),
TM quest (4× Primal Might ~400g — buy, or self-transmute for ~365g over 4 CDs),
Skyfire recipe (~5g, needs Hellfire-fort Honored — a few Ramparts runs if she skipped HFP).
Second slot: **Herbalism** (free; flight-form gathering supplies the alchemy fleet).
→ ~50g/day parked at the AH. Breakeven ~12 days.

**5. Hektorion + restored hunter — alchemy now, spec later (~200g each now).**
Alchemy 1→350 immediately (usable regardless of level), recipe at Honored
(free via Hellfire questing). They transmute **un-specced** (~22g/day each) while
being leveled at leisure; at 68, TM quest (~400g each) doubles them to ~50g/day.
Leveling itself is the fun budget, not a cost.

**5b. Warrior's Leatherworking — once he's 70 and tanking (~3,080g, or ~650g net if
selling as he levels).** Only worth starting when he actually runs heroics: nethers →
Nethercobra/Nethercleft at ~115g each, Cobrahide/Clefthide (Honored, no nether) earning
during the rep grind, and **Drums of Battle for his own tanking** (LW 350 to use).
Hellfire heroics fill Thrallmar/Honor Hold, Coilfang fills Cenarion — the same runs that
drop the nethers. **Hunter's LW is optional** and deliberately unprioritised; if he ends up
parked, Alchemy alone is the point, and a gathering profession beats LW if a farm becomes
relevant (pet tanking makes hunters efficient farmers).

**6. Optional — Xyrec's Scryers exalted (~615g in Sunfury Signets).**
Only if the mage sees play/heroics: 1,042 signets @ ≤70–80s (snipe over days, book is
thin), unlocks Runic Spellthread. Her 7 banked nethers + 2 badge-buys = ~790g back on
the first batch → instant breakeven, then nether-limited (~88g each). Otherwise skip;
signets will still exist later.

## Phase-launch playbook (~2–3 weeks out)

- **Stockpile during the lull**: primals (Air/Fire/Mana), Fel Lotus + flask herbs,
  a few banked Skyfires/Chaotics, the paladin's surplus nethers. Prices and volume
  jump with the tier; production cost doesn't.
- **Decision: Yrsadriel TM → Elixir Master** the week before launch *if* an active
  1h/day AH business is wanted: flasks are ~breakeven for non-spec crafters, EM's
  ~20% yield is the whole margin; launch-month EM plausibly 300–600g/day vs TM's 60–70g.
  The lost transmute CD moves to the next leveled alt.
- Spellthread/leg-armor demand spikes with gear resets — sell into launch week, not before.

## Income model (steady state, 3 heroics/day)

| Stream | g/day |
|---|---|
| Xyrekk: tanking (bracers + shards + badges + flat loot) | ~600 |
| Yrsadriel: TM Skyfire → Chaotic cut | ~60–70 |
| Xycaelis: TM Skyfire/Earthstorm | ~50 |
| Hektorion + hunter (un-specced → 68+) | ~45 → ~100 |
| Xyrec: bags/threads/cloth CD | ~25–40 |
| **Total** | **~780–860** |

Diversify transmutes if Skyfire's book crowds: Earthstorm (~37–45g free-gems),
Primal Might (~24–34g, deepest market at ~124 sold/day region), or sell uncut.

## Tooling (all in ~/ccsandbox/wow)

- `primal-nether-analysis/` — `analyze.py` (nether craft report), `leveling_cost.py`
  (per-profession leveling cost, `--resell`, `--start/--cap`), `build_nether_page.py`
  (sortable ledger → artifact), extract_*.lua (Zygor/AtlasLoot/Questie parsing).
- `wow-tools/nether-sim/` — Monte Carlo tanking-income simulator (`cargo run --release`).
- Data source: TSM app `AppData.lua` (base-32; refresh = let TSMApplication sync).
- Ledger artifact: https://claude.ai/code/artifact/7dcfd310-e7fe-4f78-9bd8-3f6f7a21da91

## Key numbers to remember

- Primal Nether ≈ **120g** (LW leg armor), **~300–600g** via BS bracers/Iceguard (first ~5/wk).
  Badges buy no nethers this phase. TSM mat-cost tip: set Primal Nether to `0c` and encode the
  opportunity cost as the Crafting operation's **Min Profit (~100g)** — a single mat price can't
  be right for every character since nethers are BoP and the setting is factionrealm-wide.
- Skyfire transmute EV ≈ **46–58g/day** (free gems); un-specced ≈ 22g/day.
- Heroic tanking ≈ **165–210g/run** all-in ≈ 230–320g/hour.
- Break-even snapshots: bracer plans ~1–2 crafts; TM alt ~12 days; enchanting-on-tank
  ~3 weeks of shards (but it's permanent infrastructure).
