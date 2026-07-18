# WeakAura Dev Environment for TBC Anniversary — Design

**Date:** 2026-07-18
**Status:** Approved
**Goal:** A class-agnostic development environment for programmatically inspecting, migrating, restyling, validating, and deploying WeakAuras for WoW: The Burning Crusade Anniversary Edition (client 2.5.6, build ~68775).

## Problem

The user's WeakAuras pack (470 auras, account THESNUB) was partially machine-migrated from a vanilla/SoD-era pack. Migrations of this kind repeatedly hit the same failure modes:

1. No trusted source for "does spell X exist / what is its ID at this rank" in the *current* Anniversary client — model memory and wikis are unreliable (the game re-releases change spell availability over time; e.g. Ice Lance exists in TBC Anniversary despite not existing in original 2007 TBC).
2. Hand- or ad-hoc-tool edits corrupt structure (e.g. a `dynamicgroup` whose children were deleted but which still exists as an empty husk; stale template spell references like paladin Divine Shield inside shaman trinket auras).
3. Restyling donor auras from other packs to match the user's visual style is manual and error-prone.

The intended workflow: grab specific auras from updated TBC packs (or the user's own broken set), keep their *logic*, apply the user's pack's *look*, validate all spell facts against the real client, and land them safely in `WeakAuras.lua`.

Fixing specific classes (shaman first, then mage) is **deferred** — it becomes the first use of this pipeline, not part of it.

## Decisions

- **Approach:** Lua-first toolchain reusing WeakAuras' own serialization libraries (approved over Python-only and in-game-centric alternatives).
- **Delivery:** the pipeline writes `WeakAuras.lua` (SavedVariables) directly, game closed, with mandatory backups. Import strings remain available as a secondary output.
- **Ground-truth rule:** no spell/talent fact enters an aura without validating against client-derived data. Model memory and wikis produce hypotheses only.

## 1. Repo layout (`~/ccwow`)

```
ccwow/
├── CLAUDE.md                  # env conventions + workflow rules
├── tools/
│   ├── wa-codec/              # Lua 5.1 CLI: decode/encode !WA:2! strings
│   │   └── libs/              # vendored LibSerialize, LibDeflate (unmodified, from WeakAuras2)
│   ├── sv/                    # SavedVariables load/save (Lua, dofile-based)
│   └── migrate/               # Python: diff, style templates, batch reports
├── data/
│   ├── ground-truth/          # spell/talent dumps from the client (JSON)
│   └── auras/                 # decoded auras as JSON: mine/, donors/, out/
├── refs/                      # read-only clones (gitignored)
│   ├── WeakAuras2/            # aura schema: Prototypes.lua, region files
│   └── wow-ui-source/         # branch classic_anniversary — API truth
├── addon/XyrecDump/           # in-game dump addon (ground-truth oracle)
├── backups/                   # timestamped WeakAuras.lua backups (gitignored)
└── docs/superpowers/specs/    # design docs
```

Everything under git; `refs/` and `backups/` gitignored. `data/auras/mine/` holds the pack's decoded state so every migration step is diffable history.

Game paths (fixed):
- SavedVariables: `/Applications/World of Warcraft/_anniversary_/WTF/Account/THESNUB/SavedVariables/WeakAuras.lua`
- AddOns: `/Applications/World of Warcraft/_anniversary_/Interface/AddOns/`
- Installed WeakAuras version: 5.21.8 (TBC toc, Interface 20505/20506).

## 2. Codec (trust anchor)

Standalone Lua 5.1 (Homebrew `lua@5.1`) running vendored, unmodified LibSerialize + LibDeflate from the WeakAuras2 repo, with a minimal standalone shim (no WoW globals required by these libs).

- `wa decode <string|file>` → pretty JSON. Handles `!WA:2!` (LibSerialize) and detects legacy formats (reports them; legacy decode support only if needed).
- `wa encode <file.json>` → `!WA:2!` export string. Pipeline: LibSerialize:SerializeEx → LibDeflate:CompressDeflate(level 9) → LibDeflate:EncodeForPrint, `!WA:2!` prefix — i.e. exactly WeakAuras' `Transmission.lua` pipeline, because it *is* that code.
- **Acceptance test (blocking):** semantic round-trip — for a corpus of known-good export strings (a few auras freshly exported from the live game), `decode(encode(decode(s)))` must deep-equal `decode(s)`, and `encode` output must import cleanly in the WeakAuras UI in-game. Byte-identity is NOT required (serialization depends on table iteration order), but deep-equality is. No SavedVariables write capability is enabled until this passes.

JSON↔Lua-table mapping notes: WA tables mix array and hash parts and use numeric keys; the codec must preserve key types (a JSON object with key `"1"` vs array index 1) via an explicit convention, verified by the round-trip test.

## 3. SavedVariables I/O

`WeakAuras.lua` is valid Lua. Loader: `dofile` in a sandboxed environment (empty env table; capture the `WeakAurasSaved` global). No regex/text parsing.

Writer: serializes back in Blizzard's SavedVariables style — tab indentation, `["key"] = value` — with deterministic (sorted-key) ordering so repeated writes are stable and diffable. Byte-identity with Blizzard's own output is not a goal (Blizzard's key order is unspecified, and the client rewrites the file on next logout anyway). Acceptance test: `load(save(load(f)))` deep-equals `load(f)`, and the game loads the written file without error. Fine-grained change tracking lives in the git-tracked decoded JSON (`data/auras/mine/`), not in the SavedVariables diff.

Safety on every write:
1. Refuse if the WoW client process is running (it overwrites SavedVariables on logout/reload).
2. Timestamped backup to `backups/` first.
3. Atomic write (temp file + rename).
4. Post-write reload check: loader re-reads the written file successfully.
5. `wa restore <backup>` for one-command rollback.
6. The pipeline never deletes an aura without an explicit `--delete <id>` naming it.

## 4. Ground truth

Two layers; the client wins on conflict.

**XyrecDump addon** (in `addon/XyrecDump/`, symlinked or copied into the game's AddOns folder):
- `/xdump spells [from-to|list]` — walks spell IDs through `GetSpellInfo()`, records name/rank/icon for IDs that exist.
- `/xdump talents` — walks `GetTalentTabInfo`/`GetTalentInfo` for the logged-in class: tabs, talent names, ranks, positions.
- `/xdump auras` — snapshots the player's current buffs/debuffs (for capturing live proc/buff IDs).
- Output goes to the addon's SavedVariables; `tools/migrate/pull-groundtruth` imports it into `data/ground-truth/*.json`.

**wago.tools db2 exports** for the exact installed build (Spell, SpellName, Talent and related tables) → CSV/JSON in `data/ground-truth/db2/`. Used for bulk/offline queries (name → all rank IDs, talent tree structure). Cross-checked against in-game dumps.

**Encoded rule (CLAUDE.md):** any spell/talent reference written into an aura must resolve against `data/ground-truth/`; validation failures block the write and are reported, never silently passed.

## 5. Migration workflow (spell-by-spell)

Per aura:
1. **Ingest:** `wa decode` the donor export (other pack, wago.io, or an aura extracted from the live file) → `data/auras/donors/<id>.json`.
2. **Extract logic:** triggers, conditions, load rules, custom code. Validate every spell name/ID against ground truth; produce a per-aura report (exists? rank? name match? load conditions valid for TBC — e.g. talent-based spec detection, since 2.5.x has no retail specialization API).
3. **Apply style template:** presentation fields (size, anchors, offsets, font, colors, glow, cooldown swipe/edge, sub-regions, frame strata) copied from a designated exemplar aura of the user's pack (per regionType: icon, aurabar, group...). Group membership set explicitly; the tool owns both sides of the `parent`/`controlledChildren` link.
4. **Review:** emit to `data/auras/out/<id>.json`; show a structured diff (logic kept, presentation replaced, spells validated) before landing.
5. **Land:** write into `WeakAuras.lua` via the SV tool (all §3 safety steps).
6. **Verify in-game:** launch, BugSack/BugGrabber for Lua errors, visual check; `/xdump` any newly-relevant spell facts back into ground truth.

Style templates are **derived from the user's existing auras** (extracted per region type into `tools/migrate/templates/`), so "looks like my pack" is data, not code.

## 6. Validation & linting

- **Structural (`wa audit`):** invariants derived from WeakAuras' schema (refs/WeakAuras2: `Prototypes.lua`, region files): required fields per regionType, bidirectional parent/child consistency, no dangling `controlledChildren`, no empty dynamicgroups, sane `tocversion`/`internalVersion`, no cross-class stale spell refs. Runs over the whole live file; per-aura issue list. This produces the full damage report for the deferred shaman/mage work.
- **Custom code:** WA custom-code snippets extracted to `.lua` files, linted with luacheck (`std = "lua51"`) using a WoW-globals allowlist generated from `refs/wow-ui-source@classic_anniversary` `Blizzard_APIDocumentationGenerated` (script in `tools/migrate/`); WA-injected globals (`aura_env`, `WeakAuras`) appended.

## 7. Out of scope (deferred)

Shaman group repair (first real use of the pipeline), mage repair, adding new TBC abilities, wow-api-mcp MCP server installation, CI, legacy (pre-`!WA:2!`) encode support.

## 8. Risks

- **LibSerialize/LibDeflate standalone shim:** these libraries are near-pure Lua; if an unexpected WoW-global dependency appears, shim it minimally and prove correctness via the round-trip corpus.
- **JSON numeric-key fidelity:** mitigated by explicit convention + deep-equality round-trip test.
- **Writer format drift vs Blizzard's serializer:** mitigated by load→save deep-equality test plus an in-game load check.
- **wago.tools build coverage:** if the exact build's db2 export is unavailable, fall back to nearest 2.5.x build and rely more heavily on in-game dumps (which are always authoritative).
