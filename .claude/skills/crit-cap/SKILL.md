---
name: crit-cap
description: Check if a tank spec is crit-capped and suggest upgrades if not
---

Check a tank's crit cap status. If the user did not provide a spec argument, ask which tank spec: prot-paladin, prot-warrior, or feral-tank-druid.

Run the command:

```
make crit-cap SPEC={spec}
```

If the user provides arguments, they may override defaults:
- A different source filter (e.g. "all", "dungeon", "raid") -> use --source {value}

Look at the output:

- **If the output says "CRIT CAPPED!"** -- just tell the user they're crit-capped with their current defense and resilience numbers. No gear suggestions needed.

- **If there is a gap** -- present a concise summary:
  1. Current defense + resilience vs the cap. Mention both paths (pure defense rating needed OR resilience rating needed).
  2. Biggest easy wins -- slots with 0 defense where upgrades exist (BoE items, normal dungeon drops).
  3. Top 3-5 upgrades to prioritize, sorted by defense gain per effort.
