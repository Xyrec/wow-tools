---
name: check-gear
description: Check a shaman's equipped gear against BiS lists and show upgrade priorities
---

Run the bis-gear checker for a specific spec. If the user did not provide a spec argument, ask: "Which spec should I check -- Resto, Elemental, or Prot Paladin?"

Spec aliases:
- "resto" or "resto-shaman" -> --spec resto
- "ele", "elemental", or "elemental-shaman" -> --spec ele
- "prot", "prot-paladin", or "prot-pala" -> --spec prot-paladin

Run the command:
```
uv run bis-gear --spec {spec}
```

Present the results with a concise summary focusing on:

1. **Slot overview** -- How many slots are already BiS in the current phase vs. how many have available upgrades.
2. **Top 3 priority dungeons** -- From the ranked dungeon list, explain WHY each is high value (e.g. "Heroic Old Hillsbrad drops 2 upgrades AND gives Keepers of Time rep toward your BiS wrist"). Call out any normal-mode drops as easy wins (no heroic key needed).
3. **Reputation goals** -- Highlight factions close to completion (small remaining rep) and what they unlock.
4. **Raid upgrades and SR priorities** -- For each raid with soft reserves > 0, provide a full numbered soft-reserve priority list ranking ALL upgrade items by value (BiS before Option, higher score first). Recommend which items to SR but note fallbacks. For raids with SR = 0, note it is master looter.
5. **IMPORTANT: Always specify which phase an item's rank comes from.** Items marked "[Phase 0 only]" are outdated. Never say just "BiS" -- say "Phase 1 BiS" or "Phase 0 only Option (outdated)".
6. Single items can be soft-reserved more than once to increase odds of winning -- factor this into SR recommendations for high-value items.

Do NOT read bis_gear.json or source code manually -- the script handles all logic.
