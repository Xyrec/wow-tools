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
cargo run -- check --spec {spec}
```

Present the results with a concise summary focusing on:

1. **Slot overview** -- How many slots are already BiS in the current phase vs. how many have available upgrades.
2. **Top priority dungeons** -- From the ranked dungeon list, explain WHY each is high value. Items tagged `+ Future Phase BiS/Option` stay relevant into the next phase and score higher — call this out as future-proofing when recommending. Include heroic dungeons prominently -- heroic runs are strictly better than normal (they drop heroic-only items, normal items, AND give reputation). Don't separate heroic from normal or defer heroic to a secondary list. If a dungeon has heroic-only drops, that makes it MORE valuable, not less. Call out when a normal-mode run also works if the player hasn't unlocked heroics yet.
3. **Reputation goals** -- Highlight factions close to completion (small remaining rep) and what they unlock.
4. **Raid upgrades and SR priorities** -- For each raid with soft reserves > 0, provide a full numbered soft-reserve priority list ranking ALL upgrade items by value. Within the same rank (e.g. multiple BiS items), respect the ordering from the script output -- items listed earlier in the BiS list are ranked higher by the source data and should be prioritized. For example, a spell damage weapon ranked #1 in the list should be recommended over a tanking weapon ranked #3, even though both are "BiS". Recommend which items to SR but note fallbacks. For raids with SR = 0, note it is master looter.
5. **IMPORTANT: Always specify which phase an item's rank comes from.** Items marked "[Phase 0 only]" are outdated. Never say just "BiS" -- say "Phase 1 BiS" or "Phase 0 only Option (outdated)".
6. Single items can be soft-reserved more than once to increase odds of winning -- factor this into SR recommendations for high-value items.

Do NOT have a separate "Easy Wins" or "Normal Mode" section -- this is redundant with the priority dungeon list. All dungeon recommendations should be in one unified list.

Do NOT read bis_gear.json or source code manually -- the script handles all logic.
