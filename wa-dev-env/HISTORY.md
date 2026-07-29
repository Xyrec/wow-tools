# History — how this environment got here

Short narrative for fresh sessions. Operational rules live in `CLAUDE.md`;
this is the *why*.

## The arc

1. **Origin (July 2026, MacBook).** Xyrec liked the look & feel of the
   "Sabimaru" Season-of-Discovery WeakAura class packs and wanted them on
   TBC Anniversary (client 2.5.6). The first system migrated the shaman pack
   imperatively: scripts dropped SoD-rune auras, repointed SoD spell ids to
   TBC, renamed everything `Xyrec Shaman - *`, and transplanted a wago
   swing-sync timer into the pack's skin.
2. **Drift (late July, after moving to the CachyOS PC).** Weeks of direct
   live evolution (new TBC auras, layout changes, fixes) made the scripts
   unable to reproduce the live group — rebuilding would have regressed ~10
   landed changes. Verdict from Xyrec: **"Sabimaru should only ever have been
   inspiration — I wanted the look and feel, not to modify it."**
3. **The refactor (2026-07-29).** Rebuilt as a declarative system:
   `styles/xyrec.json` (the extracted look), archetype factories, per-class
   definitions, a deterministic builder, and byte-parity tests against live
   snapshots. The shaman was decompiled from its live snapshot (parity-exact),
   then re-landed once with 92 pieces of inert donor residue scrubbed.
   The old scripts moved to `tools/migrate/archive/`.
4. **The purge.** All nine in-game Sabimaru packs were deleted (plus 306
   orphaned children with broken parent links). The donors survive as
   reference JSON in `data/auras/donors/`.
5. **New classes.** Paladin, then Mage, generated through the class-agnostic
   importer (donor logic, Xyrec styling), then improved through in-game QA
   round-trips. Each import taught the pipeline something — labels, code
   fields, resource-alpha rules, coverage gaps — all folded into
   `import_donor.py` so later classes inherit every lesson.

## Hard-won gotchas (do not relearn these)

- **Lint allowlist ≠ client API.** `OffhandHasWeapon()` was in
  `.luacheckrc-wow` but does not exist in 2.5.6 — it errored in-game. Use
  idioms the installed WeakAuras addon itself uses (e.g.
  `UnitAttackSpeed("player")` off-speed for dual-wield detection).
- **Classic totem names carry rank suffixes.** `GetTotemInfo` returns
  "Fire Nova Totem VII"; exact name matching silently fails — use the totem
  trigger's pattern/find matching.
- **TBC mana ticks vs mp5 streams.** The classic tick-tracker reset on any
  mana gain; Mana Spring/Water Shield/Judgement of Wisdom made it useless.
  The fix (in shaman + ported at import): track CLEU
  `SPELL_(PERIODIC_)ENERGIZE` amounts and only treat unexplained gains as
  the 2s regen tick. "Drink" is deliberately not filtered (drink-walking
  reads sip timing off the spark).
- **Anniversary backports live above id 200000** (e.g. Seal of the Martyr
  348700, the Alliance Seal of Blood). The in-game dump must be taken with
  `/xdump spells 1 400000`. A donor tracking a spell that Anniversary
  *replaced* can't be caught by reference-validation — only by play.
- **Numeric aura names are ids.** WA resolves `auranames: ["8050"]` via
  `GetSpellName` at trigger compile — rank-agnostic name matching. Trust
  `BuffTrigger2.lua` over assumptions.
- **Empty Lua tables are one type.** The codec emits `[]` where Python wrote
  `{}`; parity normalizes them equal. Floats survive Lua serialization only
  to ~14 digits; parity rounds to 9.
- **SoD packs contain donor residue everywhere**: bogus `class.multi`
  entries, unused race/talent/size blobs, dead `auranames` lists,
  never-firing gates (`not_spellknown: 642` = paladin Divine Shield on
  shaman auras). `tools/build/scrub.py` recognizes the classes; imports
  scrub automatically.
- **Stale client sessions lie.** Several "bugs" were the user's game client
  holding pre-land state — a land while the game runs gets clobbered on
  logout (the guard exists because this happened), and QA observations from
  a session older than the last land are misleading. Reload first.
- **Seal twisting math (paladin Weapon Swing bar):** ticks at 0.4s
  (twist-cast window) and 1.6s/3.1s (one/two GCD budget) — donor-tuned,
  verified valid for TBC.
