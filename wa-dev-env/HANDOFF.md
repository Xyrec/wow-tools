# Session handoff — WeakAura dev environment (2026-07-18, MacBook)

State at handoff: environment complete and verified; `Xyrec - Shaman` (36 auras,
incl. the tazUI swing-sync timer transplant) is live and validated; the old
`Sabimaru - Shaman Classic [SoD]` group is intact but disabled (`load: never`).

## Portable backups (work on any machine)
- `data/auras/mine/xyrec-shaman-live.json` — the full landed group, decoded
- `data/auras/mine/xyrec-shaman-import.txt` — `!WA:2!` string; paste into
  WeakAuras → Import on any client to get the exact group
- `data/auras/mine/sabimaru-live.json` — the old group (presentation source)
- `data/ground-truth/` — client dumps (build 2.5.6.68775) + db2 CSVs

## Machine-specific paths to update on a new machine
- `tools/sv/sv.lua` → `LIVE_PATH` (WeakAuras.lua SavedVariables path)
- `tools/sv/groundtruth.lua` → `DUMP_PATH` (XyrecDump SavedVariables path)
- `tools/migrate/fetch_db2.py` → `BUILD_INFO` (WoW root `.build.info`)
- `tools/install-addon.sh` → `DST` (AddOns folder)
- `tools/sv/safety.lua` → game-process check is macOS `pgrep`; adjust for
  Windows (e.g. `tasklist | findstr Wow`)
- `tests/run.sh` — needs `luajit` (Lua 5.1-compatible) + `uv` + `luacheck`

## Where things are
- Spec: `docs/superpowers/specs/2026-07-18-weakaura-dev-environment-design.md`
- Plan: `docs/superpowers/plans/2026-07-18-weakaura-dev-environment.md`
- Workflow + ground-truth rule: `CLAUDE.md` (this directory)
- Reports: `data/reports/` (shaman/mage damage, SoD→TBC diff)
- Deterministic builds: `tools/migrate/build_xyrec_shaman.py` (+ `--bake-scale`
  opt-in, currently off — caused overlap), `tools/migrate/build_xyrec_swingtimer.py`

## Open threads
- User wants to re-group/re-arrange the Xyrec layout manually (export + fold
  back into build script afterwards)
- Mage group: parked; baseline report in `data/reports/mage-damage.md`
- Optional additions not yet done: Heroism, Fire/Earth Elemental, Tremor Totem
- Swing timer: OH/Sync bars could be gated behind Dual Wield for Ele/Resto
- `refs/` clones (WeakAuras2, wow-ui-source@classic_anniversary) are gitignored —
  re-clone on the new machine (see plan Task 12)
