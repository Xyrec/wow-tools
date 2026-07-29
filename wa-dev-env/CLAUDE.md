# World of Warcraft Development Environment for Claude

> **Location note:** this environment lives in `wa-dev-env/` inside the
> `wow-tools` repo (repo root is a separate Rust BiS-checker project — see root
> `AGENTS.md`, which does NOT apply here). ALL commands below run from THIS
> directory — `cd wa-dev-env/` first.

## Purpose

Xyrec's WoW development environment for **The Burning Crusade Anniversary
Edition** (client 2.5.6). Focus: **WeakAura development** — the `Xyrec - <Class>`
groups are built declaratively from this repo and landed into the live
SavedVariables. Also: addon development (`addon/XyrecDump`) and ad-hoc WoW
questions. Read `HISTORY.md` for how this architecture came to be and the
hard-won gotchas — worth skimming before touching anything.

## Working agreements

- **Claude owns commits and pushes.** Don't ask; commit at natural completion
  points in the house style: terse conventional subjects
  (`feat:`/`fix:`/`chore:`), body only when genuinely needed, no trailers.
  Aura lands commit their refreshed `data/auras/mine/` snapshots together
  with the defs that produced them. Push freely.
- **Design interviews** use the user's `/grill-me` skill (one question at a
  time, each with a recommendation). **Planning** uses Claude Code's native
  plan mode. Do not use plugin-provided process/spec/brainstorming workflows.
- For visual/design changes: implement, land, let the user QA in-game, fold
  feedback. The user reports observations; don't argue with them — verify in
  data (they have repeatedly been right).

## Machine setup

Per-machine paths and the game-running guard live in ONE place:
`tools/sv/machines.lua` (selected by `uname`; currently Linux = CachyOS PC
with Lutris/Proton, Darwin = MacBook). `tools/migrate/fetch_db2.py` mirrors
the WoW-root per platform. To add a machine: add a CONFIGS entry.

Dependencies: `luajit` (Lua 5.1-compatible; runs the codec + SavedVariables
tools), `luacheck` (lints aura Lua against `.luacheckrc-wow`), `uv` (Python
runner; `pyproject.toml` pins python >= 3.14, pytest via dev group).
In-game addon: `./tools/install-addon.sh` installs XyrecDump from `addon/`.

## Build system (primary — tools/build/)

Groups are DECLARATIVE: `styles/xyrec.json` (the look, as data) + archetypes
+ `auras/<class>/` (group.json, defs/, lua/) compose into full payloads.
The live snapshots under `data/auras/mine/` are pinned by parity tests —
never hand-edit built output; edit defs/style and rebuild.
- `python3 tools/build/build_group.py <class> -o out.json [--scrub] [--displays]`
- `python3 tools/build/parity.py BUILT.json SNAPSHOT.json [--only "<id>"] [--diff-payloads]`
- `python3 tools/build/decompile.py SNAPSHOT.json --class <class> [--cruft-report]`
  — fold in-game hand-tweaks back into defs after a QA session
- `python3 tools/build/import_donor.py DONOR.json --class <class> [--report]`
  — new-class baseline from a donor pack (manifest + spellmap contract)
Sabimaru donor packs (`data/auras/donors/`) are REFERENCE ONLY — inspiration
and import inputs, never modified, never landed. Superseded imperative tools
live in `tools/migrate/archive/`.

Classes live so far: **shaman**, **paladin**, **mage** (each with parity
tests). Remaining donors: druid, hunter, priest, rogue, warlock, warrior.

## Commands (codec / gates)

- `./tools/wa decode <string|@file>` / `./tools/wa encode <json>` — !WA:2! codec
- `./tools/wa extract "<id>" -o f.json` / `./tools/wa land f.json [--parent "<id>"] [--delete]`
- `./tools/wa backup` / `./tools/wa restore backups/<file>` / `./tools/wa delete "<id>"` / `./tools/wa dump-displays`
- `python3 tools/migrate/validate_spells.py <payload.json>` — spell gate (must pass pre-land)
- `python3 tools/migrate/audit.py [displays.json]` — structural + style-canon audit
- `python3 tools/migrate/extract_custom_code.py [displays.json] -o tmp/snippets && luacheck --config .luacheckrc-wow tmp/snippets/`
- `./tests/run.sh` — full test suite (Lua via luajit, Python via uv+pytest)

## Build loop (per class)

1. edit `styles/xyrec.json` or `auras/<class>/` (defs, lua, group.json)
2. `build_group.py <class>` → parity (classes with snapshots)
3. validate_spells + audit + luacheck (via `--displays`)
4. `wa land` (auto-backup, game-closed guard) → in-game QA + BugSack
5. `wa extract` → refresh `data/auras/mine/<class>` snapshot + import string
6. hand-tweaks made in-game? `decompile.py` the fresh snapshot to fold them
   into defs, re-run parity, commit

## Session playbook (hard-won operational patterns)

- **Never pipe gate commands through `tail`/`head`/`grep -c`** — the pipeline
  exit code masks failures (this bit us three times). Redirect to a log file
  and `grep -q` it: `./tools/wa land X > tmp/land.log 2>&1; grep -q "^landed:" tmp/land.log || ...`
- **Shutdown lag:** the client keeps running ~5–20s after the user exits;
  the guard rightly blocks. Retry pattern: loop 2–3 times with `sleep 6`.
- **The user is often in-game while reporting.** Prepare everything, attempt
  the land; if the guard blocks, say "exit and say go" and wait. NEVER work
  around the guard — an in-game session clobbers landed changes on logout.
- **Parity-red lifecycle:** editing defs makes that class's parity test fail
  until the change is landed and the snapshot re-extracted. That's expected;
  land + extract + (if wiring changed) sync `group.json` `child_order` from
  the fresh snapshot's `c` order.
- **`wa land --delete` only replaces incoming ids** — auras removed from a
  group linger as orphans; `wa delete` them and re-check `audit.py`.
- **Ground truth refresh:** in-game `/xdump spells 1 400000` (covers the
  3xxxxx Anniversary backports; e.g. Seal of the Martyr 348700) +
  `/xdump talents`, `/reload`, then `./tools/wa pull-groundtruth`.
- **Import coverage gap:** the importer validates donor *references*, not
  *coverage* — TBC spells the SoD-era donor never knew (Avenging Wrath,
  Water Elemental) must be checked by name against ground truth and added
  as defs. Ask the user which; spec matters.

## Ground-truth rule (HARD)

No spell/talent fact enters an aura unless it resolves against
`data/ground-truth/` — the in-game dump (`spells.json`, authoritative) or
the db2 CSVs (`db2/`, fallback tier; validate_spells tags which matched).
Model memory, wikis, and "I'm sure it exists" are hypotheses only. This
applies to API names in custom Lua too: check `.luacheckrc-wow` AND prefer
idioms used by the installed WeakAuras addon itself — a name being in the
lint allowlist does not prove the client exposes it (see HISTORY.md).
Note: db2 SpellName contains ALL records incl. NPC spells; "player-usable"
needs the in-game dump.

## Key external resources

- **API ground truth:** `refs/wow-ui-source` @ `classic_anniversary`
  (github.com/Gethe/wow-ui-source; re-clone if missing — gitignored) and the
  INSTALLED addon (`<wow_root>/Interface/AddOns/WeakAuras`, 5.21.8):
  `Transmission.lua` (export format), `BuffTrigger2.lua` / `GenericTrigger.lua`
  / `Prototypes.lua` (trigger/load semantics — read before asserting WA
  behavior). Our codec vendors the addon's own LibSerialize/LibDeflate.
- **Spell/db2 data:** wago.tools CSV exports per build (`fetch_db2.py`).
- **Community docs:** warcraft.wiki.gg; wowtbc.gg class guides (rotations);
  wago.io data API (`data.wago.io/lookup/wago?id=<slug>`).
- **In-game errors:** BugSack/BugGrabber (installed). SavedVariables write on
  `/reload`/logout — never edit the live file by hand or with regex; writes
  go through `tools/sv/safety.lua` only (guard, timestamped backup in
  `backups/`, atomic verified write).
