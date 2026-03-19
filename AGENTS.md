# TBC Shaman BiS Gear Checker (Resto / Elemental)

## What This Project Does

Compares a WoW TBC Shaman's equipped gear against Best-in-Slot (BiS) lists to find actionable upgrades from dungeons and reputations. Supports Resto and Elemental specs.

## Project Structure

```
bis-gear/
  pyproject.toml          # Python project config with CLI entry points
  data/
    resto.json            # Resto Shaman character data (paste updated exports here)
    elemental.json        # Elemental Shaman character data
    current-phase.txt     # Single line like "phase-1" — which phase to check against
    soft-reserves.txt     # Soft-reserve counts per raid (0 = master looter)
  output/
    resto-shaman/
      bis_gear.json       # Generated BiS data for Resto (all phases), output of bis-parse
    elemental-shaman/
      bis_gear.json       # Generated BiS data for Elemental (all phases), output of bis-parse
  src/bis_gear/           # Python package
    check_gear.py         # Main tool — compares gear against BiS lists
    parse_bis.py          # HTML parser — regenerates bis_gear.json from source HTML
  sources/
    wowhead/
      resto-shaman/       # phase-0.html through phase-5.html (Resto BiS pages)
      elemental-shaman/   # phase-0.html through phase-5.html (Elemental BiS pages)
```

## How to Use

```bash
# Check gear against BiS lists (--spec required):
uv run bis-gear --spec resto              # loads data/resto.json by default
uv run bis-gear --spec ele                # loads data/elemental.json by default
uv run bis-gear --spec resto custom.json  # explicit character file
echo '{"character": {...}}' | uv run bis-gear --spec ele -

# Spec aliases: resto, resto-shaman | ele, elemental, elemental-shaman

# Regenerate bis_gear.json from source HTML (only if HTML files change):
uv run bis-parse --spec resto
uv run bis-parse --spec ele
```

## Development

A git pre-commit hook runs `ruff check`, `ty check`, and `ruff format` automatically before every commit. Commits are blocked if lint or type errors exist. Formatting is applied and staged automatically if checks pass.

### Expected Input Format

The character JSON should have this structure (top-level `"character"` wrapper is optional):

```json
{
  "character": {
    "name": "Name",
    "class": "Shaman",
    "equippedItems": [
      {"slot": 1, "slotName": "Head", "itemId": 29028, "itemName": "Cyclone Headdress"},
      ...
    ],
    "reputations": [
      {
        "group": "Outland",
        "factions": [
          {"name": "Cenarion Expedition", "standing": "Revered", "currentRep": 18323, "requiredRep": 21000, "remainingRep": 2677}
        ]
      }
    ]
  }
}
```

Valid `slotName` values: `Head`, `Neck`, `Shoulder`, `Back`, `Chest`, `Wrist`, `Hands`, `Waist`, `Legs`, `Feet`, `Finger 1`, `Finger 2`, `Trinket 1`, `Trinket 2`, `Main Hand`, `Off Hand`, `Ranged`.

### Phase Priority

The current phase (from `current-phase.txt`) is **authoritative**. Phase 0 is only a fallback for items not listed in the current phase at all. An item that was BiS in Phase 0 but doesn't appear in Phase 1 is labeled `[Phase 0 only]` and scores lower in the priority list.

### What It Outputs

The script outputs these sections in order:

1. **{Phase} BiS (you're set)** — Slots where equipped gear is BiS in the current phase.
2. **{Phase} Option (upgrade available this phase)** — Slots where equipped gear is listed as an Option in the current phase.
3. **Phase 0 Only (outdated)** — Slots where gear was BiS/Option in Phase 0 but isn't listed in the current phase at all.
4. **Not on Any BiS List** — Slots where equipped gear doesn't appear on any checked BiS list.
5. **Priority: Dungeons to Run** — Dungeons ranked by value-per-run score, with a breakdown of what contributes to each score. Scoring:
   - Scores use a 100-point scale with phase decay (each phase behind current halves the score):
   - Current-phase BiS: **100**, Option: **80**
   - 1 phase behind BiS: **50**, Option: **40**
   - 2 phases behind BiS: **25**, Option: **20** (and so on, halving each phase)
   - Heroic badges toward badge vendor items: **+10% of total badge vendor item scores**
   - Rep toward needed faction vendor items: **sum of those items' individual scores**
   Shows what drops in that dungeon, and what reputation vendor items the run also earns progress toward.
6. **Reputation Goals** — Factions to grind, what vendor items they unlock, total rep needed to the required standing (e.g. "need Exalted, ~8,415 rep to go"), and which dungeons give that rep.
7. **All Upgrades by Slot** — Full per-slot breakdown tagged `[D]` (dungeon), `[R]` (reputation), or `[B]` (badges), with `(H)` for heroic-only. Shows rep progress for reputation items.
8. **Raid Upgrades** — Raid BiS/Option items grouped by raid instance (or grouped raids like Gruul+Mag). Shows soft-reserve count from `data/soft-reserves.txt` (0 = "master looter", N = "N soft reserves"). Items sorted by score within each raid.
9. **No Dungeon/Rep/Raid Upgrade** — Slots needing crafting, world bosses, etc.
10. **Summary** — Slot counts by tier and upgrade availability (dungeon/rep and raid counted separately).

Items are deduplicated across phases and across shared slots (rings, trinkets). Items already equipped in another slot are excluded from upgrade recommendations. World drops, classic raids, PvP, and profession-only items are filtered out of the upgrade list. Raid items (Karazhan, Gruul's Lair, etc.) are shown in their own section. The script auto-detects Alliance/Horde based on reputation data for Hellfire dungeon faction mapping.

### Soft-Reserve Config

The file `data/soft-reserves.txt` controls soft-reserve counts per raid. Format:

```
# Lines starting with # are comments
karazhan=2
gruuls-lair+magtheridons-lair=1    # + groups raids sharing an SR pool
serpentshrine-cavern=0              # 0 = master looter (no SR info shown)
```

- Use `+` to group raids that share a soft-reserve pool (e.g. Gruul+Mag run together with 1 shared SR).
- A raid tag must not appear both individually and in a group (the script errors if it does).
- All TBC and WotLK raids are listed with available tags shown in comments.

## When the User Asks to Check Gear

1. **Ask which spec** if the user hasn't specified: "Which spec should I check — Resto or Elemental?"
2. Run `uv run bis-gear --spec resto` or `uv run bis-gear --spec ele` (no filename needed — defaults to `data/resto.json` or `data/elemental.json`).
3. Present the results to the user with a concise summary. Focus on:
   - How many slots are already BiS vs. have available upgrades.
   - The **top 3 priority dungeons** from the ranked list — explain *why* each is high value (e.g. "Heroic Old Hillsbrad drops 2 upgrades AND gives Keepers of Time rep toward your BiS wrist").
   - Any reputation goals that are close to completion (small remaining rep).
   - Call out any normal-mode dungeon drops (no heroic key needed) as easy wins.
   - Highlight notable **raid upgrades** — mention the raid instance, how many soft reserves the user has, and the highest-value items. If SR count is 0, note it's master looter.
   - For each raid with SR > 0, provide a **soft-reserve priority list**: rank ALL upgrade items from that raid by value (BiS before Option, higher score first), not just the top N matching the SR count. The user needs to see the full ranked list so they can pick alternatives if someone else has already soft-reserved their top choice. Format as a numbered list like "1. Light's Justice [BiS] (main hand) 2. Jade Ring [BiS] (ring) 3. ..." with a note like "With 2 SRs, your best picks are #1 and #2 — but if either is taken, #3-#5 are strong fallbacks."
   - Single items can be soft-reserved more than once. This lets the player roll on that item multiple times and increases their odds of winning it. High-value items will often be soft-reserved more than once by the same player in a single raid, so take that into consideration when recommending SR priorities.
   - **IMPORTANT: Always specify which phase an item's rank comes from.** Items marked `[Phase 0 only]` in the script output are outdated — they were BiS/Option in Phase 0 but are NOT on the current phase's list. Never call something just "BiS" or "Option" without saying which phase. For example, say "Phase 1 BiS wrists" or "Phase 0 only Option (outdated)" — not just "BiS wrists" or "an Option".
4. Do NOT read `bis_gear.json` or the source code manually — the script handles all the logic.
5. If the user pastes character JSON directly in chat instead of updating the spec file, save it to `data/resto.json` or `data/elemental.json` (ask which spec if unclear), then run the script.

## Slot Mapping

The BiS JSON uses these slot keys: `head`, `shoulders`, `back`, `chest`, `wrists`, `hands`, `waist`, `legs`, `feet`, `neck`, `rings`, `trinkets`, `weapons`, `offhands`/`shields-offhands` (varies by phase), `totems`/`idols` (varies by phase).
