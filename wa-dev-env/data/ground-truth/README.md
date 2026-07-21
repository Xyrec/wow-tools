# Ground truth — provenance and freshness

Client-derived spell/talent facts. The HARD rule in `../../CLAUDE.md` applies:
no spell/talent fact enters an aura unless it resolves here. In-game dumps win
over db2 on conflict (db2 SpellName contains ALL records incl. NPC spells).

## Contents
- `spells.json` / `spells_meta.json` — in-game `GetSpellInfo` scan via the
  XyrecDump addon (`/xdump spells 1 200000`). Meta records build + date;
  current dump: build 20506 (2.5.6), 2026-07-18, 28,336 spells.
- `talents.json` — per-class `/xdump talents`. Currently SHAMAN only; the dump
  stores RAW positional returns (client API signatures drift — interpret
  tool-side). Run on each class you work on (e.g. mage before mage work).
- `spellbook.json` — `/xdump book` per class (which spells the character knows).
- `auras.json` — live buff/debuff snapshots (`/xdump auras`).
- `db2/` — wago.tools CSV exports for the exact installed build
  (`python3 tools/migrate/fetch_db2.py`; build auto-detected from `.build.info`,
  currently 2.5.6.68775).

## Refresh procedure
In-game: `/xdump all` (or individual subcommands), wait for "done", `/reload`.
Then from `wa-dev-env/`: `./tools/wa pull-groundtruth`.

## Verified lessons (do not re-litigate from memory)
- **Ice Lance EXISTS in TBC Anniversary** — ids 30455 (+ 43427/44176/45906/46194
  variants) per both in-game dump and db2. Model/wiki priors about original-2007
  TBC do not apply to the Anniversary client.
- WeakAuras resolves spell ids to the player's highest-known rank (BuffTrigger2
  `GetSpellName` name-matching; GenericTrigger `GetEffectiveSpellId`) — rank-1
  ids in triggers are NOT a bug.

## refs/ pinning (gitignored clones, re-create per machine)
- `refs/wow-ui-source` — https://github.com/Gethe/wow-ui-source, branch
  `classic_anniversary` (client-exact Blizzard_APIDocumentationGenerated).
- `refs/WeakAuras2` — https://github.com/WeakAuras/WeakAuras2, main branch
  (schema reference + .luacheckrc source for gen_luacheckrc.py).
- Vendored codec libs in `tools/wa-codec/libs/` were copied from the INSTALLED
  WeakAuras addon (5.21.8) — version-exact to the user's client, committed, and
  do not depend on refs/.
