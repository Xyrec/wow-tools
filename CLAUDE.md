# Resto Shaman TBC BiS Gear Checker

## What This Project Does

Compares a WoW TBC Resto Shaman's equipped gear against Best-in-Slot (BiS) lists to find actionable upgrades from dungeons and reputations.

## Project Structure

```
bis-gear/
  pyproject.toml          # Python project config with CLI entry points
  data/
    character.json        # User's character data (paste updated exports here)
    current-phase.txt     # Single line like "phase-1" — which phase to check against
  output/
    bis_gear.json         # Generated BiS data (all phases), output of bis-parse
  src/bis_gear/           # Python package
    check_gear.py         # Main tool — compares gear against BiS lists
    parse_bis.py          # HTML parser — regenerates bis_gear.json from source HTML
  sources/
    wowhead/              # phase-0.html through phase-5.html (wowhead BiS pages)
    atlasloot/            # AtlasBIStooltips addon data + comparison script
```

## How to Use

```bash
# Check gear against BiS lists:
uv run bis-gear character.json
# or via stdin:
echo '{"character": {...}}' | uv run bis-gear -

# Regenerate bis_gear.json from source HTML (only if HTML files change):
uv run bis-parse
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
8. **No Dungeon/Rep Upgrade** — Slots needing raids, crafting, world bosses, etc.
9. **Summary** — Slot counts by tier and upgrade availability.

Items are deduplicated across phases and across shared slots (rings, trinkets). Items already equipped in another slot are excluded from upgrade recommendations. World drops, classic raids, PvP, and profession-only items are filtered out of the upgrade list. The script auto-detects Alliance/Horde based on reputation data for Hellfire dungeon faction mapping.

## When the User Asks to Check Gear

1. Run `uv run bis-gear character.json` (or whatever file they provide).
2. Present the results to the user with a concise summary. Focus on:
   - How many slots are already BiS vs. have available upgrades.
   - The **top 3 priority dungeons** from the ranked list — explain *why* each is high value (e.g. "Heroic Old Hillsbrad drops 2 upgrades AND gives Keepers of Time rep toward your BiS wrist").
   - Any reputation goals that are close to completion (small remaining rep).
   - Call out any normal-mode dungeon drops (no heroic key needed) as easy wins.
   - **IMPORTANT: Always specify which phase an item's rank comes from.** Items marked `[Phase 0 only]` in the script output are outdated — they were BiS/Option in Phase 0 but are NOT on the current phase's list. Never call something just "BiS" or "Option" without saying which phase. For example, say "Phase 1 BiS wrists" or "Phase 0 only Option (outdated)" — not just "BiS wrists" or "an Option".
3. Do NOT read `bis_gear.json` or the source code manually — the script handles all the logic.
4. If the user pastes character JSON directly in chat instead of updating `character.json`, save it to `data/character.json` first, then run the script.

## Slot Mapping

The BiS JSON uses these slot keys: `head`, `shoulders`, `back`, `chest`, `wrists`, `hands`, `waist`, `legs`, `feet`, `neck`, `rings`, `trinkets`, `weapons`, `offhands`/`shields-offhands` (varies by phase), `totems`/`idols` (varies by phase).
