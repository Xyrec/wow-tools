---
name: find-defense
description: Find defense rating gear upgrades for Prot Paladin toward the 490 cap
---

Find defense rating gear upgrades to help reach the 490 defense cap. Run the command:

```
uv run find-stat data/prot-paladin.txt --stat defense --target 490 --source easy
```

If the user provides arguments, they may override defaults:
- A different target number (e.g. "485") -> use --target {value}
- A different source filter (e.g. "all", "heroic", "raid") -> use --source {value}

Present the results with a concise summary focusing on:

1. **Current defense level** and how far from the 490 defense cap.
2. **Biggest easy wins** -- Slots that currently have 0 defense rating where cheap upgrades exist (BoE items, quest rewards, normal dungeon drops).
3. **Slot-by-slot breakdown** -- For each slot with an available upgrade, note the defense gain and how to obtain the item.
4. **Priority order** -- Which upgrades to pursue first based on defense gained per effort.
