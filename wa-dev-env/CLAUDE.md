# World of Warcraft Development Environment for Claude

> **Post-merge location note:** this environment lives in `wa-dev-env/` inside the
> `wow-tools` repo (repo root is a separate Rust BiS-checker project — see root
> `AGENTS.md`). ALL commands below (`./tools/wa`, `./tests/run.sh`,
> `python3 tools/migrate/...`) are relative to THIS directory — `cd wa-dev-env/`
> first. Lua runtime is `luajit` (Lua 5.1-compatible; Homebrew's `lua@5.1`
> formula is discontinued — the plan doc's Task 1 predates this).

This is a folder for scaffolding and testing various projects.

I will primarily be developing my own addons, debugging existing addons, or asking questions related to World of Warcraft.

We are currently in World of Warcraft: The Burning Crusade (Anniversary Edition).

'/Applications/World of Warcraft/_anniversary_' is the path to the game installation. (Specifically the WTF and Interface folders are likely the only relevant folders)

## WeakAura Dev Environment

Spec: docs/superpowers/specs/2026-07-18-weakaura-dev-environment-design.md

### Ground-truth rule (HARD)
No spell/talent fact may be written into an aura unless it resolves against
`data/ground-truth/` (in-game dumps win over db2). Model memory, wikis, and
"I'm sure it exists" are hypotheses only — the Anniversary client changes
spell availability over time (e.g. Ice Lance IS in the 2.5.6 client: id 30455).
Note: db2 SpellName contains ALL spell records incl. NPC spells; "player-usable"
needs the in-game dump (or IsSpellKnown checks).
Refresh: in-game `/xdump spells 1 200000` + `/xdump talents`, `/reload`,
then `./tools/wa pull-groundtruth`. Offline: `python3 tools/migrate/fetch_db2.py`.

### Commands
- `./tools/wa decode <string|@file>` / `./tools/wa encode <json>` — !WA:2! codec
- `./tools/wa extract "<id>" -o f.json` / `./tools/wa land f.json --parent "<id>" [--delete]`
- `./tools/wa backup` / `./tools/wa restore backups/<file>` / `./tools/wa dump-displays`
- `python3 tools/migrate/validate_spells.py <payload.json>` — spell gate (must pass pre-land)
- `python3 tools/migrate/restyle.py <donor.json> --template tools/migrate/templates/<t>.json -o out.json`
- `python3 tools/migrate/audit.py` — structural audit of the live file
- `python3 tools/migrate/extract_custom_code.py -o tmp/snippets && luacheck --config .luacheckrc-wow tmp/snippets/`
- `./tests/run.sh` — full test suite (Lua via luajit, Python via uv+pytest)

### Migration loop (per aura)
1. decode/extract donor → data/auras/donors/
2. validate_spells (fix unknowns via ground truth, never by assumption)
3. restyle with a template from tools/migrate/templates/
4. review diff → `wa land` (auto-backup) → `audit`
5. in-game: check visuals + BugSack; `/xdump` new facts back in

### Safety
Writes go through tools/sv/safety.lua only: game-closed guard, timestamped
backup in backups/, atomic verified write. The live SavedVariables path is in
tools/sv/sv.lua (LIVE_PATH). Never edit the live file by hand or with regex.
