#!/usr/bin/env python3
"""Build the Xyrec TBC shaman group from the ORIGINAL SoD payload.

Proper migration, replacing the old ad-hoc tool's output:
- rename all ids (Sabimaru/SoD -> Xyrec) so the group lands alongside the old one
- drop SoD-only auras and subtrees (runes, tank-role, proc textures, totem section,
  maelstrom) — subtree drops mirror the user's established preferences
- re-point SoD spell ids to their TBC equivalents (trigger fields AND load gates)
- strip SoD-only load gates that are vacuous in TBC (not_spellknown on rune ids)
- strip uid (regenerated on land) and wagoID (this is a personal fork)
All spell ids used here were verified against data/ground-truth (client dump).
"""
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "original_shaman_weakaura.json"
OUT = REPO / "data" / "auras" / "out" / "xyrec-shaman.json"

ROOT_OLD = "Sabimaru - Shaman Classic [SoD]"
ROOT_NEW = "Xyrec - Shaman"

# SoD spell id -> TBC spell id (verified in data/ground-truth/spells.json)
REPOINT = {
    408510: 24398,   # Water Shield (SoD rune -> TBC base spell)
    408514: 974,     # Earth Shield (SoD rune -> TBC resto talent spell)
    425336: 30823,   # Shamanistic Rage (SoD rune -> TBC enh 41pt talent)
}

# auras (and their whole subtrees) that have no TBC purpose
DROP = {
    "Shaman - Proc Texture",          # SoD proc textures (subtree: Power Surge/Molten Blast L+R)
    "Shaman - Totems",                # user tracks totems with other UI (subtree)
    "Shaman - Maelstrom Weapon",      # SoD rune (subtree: MW1-5)
    "Shaman - Molten Blast",
    "Shaman - Lava Lash",
    "Shaman - Lava Burst",
    "Shaman - Riptide",
    "Shaman - Healing Rain",
    "Shaman - Tidal Waves",
    "Shaman - Decoy Totem",
    "Shaman - Spirit of the Alpha",
    "Shaman - Ancestral Guidance",
    "Shaman - Flame Shock [Tank]",    # gated on SoD tank rune; no TBC tank shaman
    "Shaman - Fire Nova",             # SoD-conditional duplicate of Fire Nova Totem
}

RENAME_SPECIAL = {
    ROOT_OLD: ROOT_NEW,
    "Shaman - Flame Shock [Dps]": "Xyrec Shaman - Flame Shock",  # [Tank] dropped; suffix moot
}


def rename(old_id: str) -> str:
    if old_id in RENAME_SPECIAL:
        return RENAME_SPECIAL[old_id]
    if old_id.startswith("Shaman - "):
        return "Xyrec " + old_id
    return "Xyrec - " + old_id


def repoint_value(v):
    if isinstance(v, (int, float)) and int(v) in REPOINT:
        return REPOINT[int(v)]
    if isinstance(v, str) and v.isdigit() and int(v) in REPOINT:
        return str(REPOINT[int(v)])
    return v


def repoint_tree(node):
    if isinstance(node, dict):
        return {k: repoint_tree(repoint_value(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [repoint_tree(repoint_value(v)) for v in node]
    return node


def clean_item_trigger_residue(aura, report):
    """Item-type triggers (Weapon Enchant / equipment cooldowns) ignore spell
    fields entirely — strip the stale ones so future analysis stays clean."""
    trigs = aura.get("triggers")
    if not isinstance(trigs, dict):
        return
    for key, val in trigs.items():
        if isinstance(val, dict) and isinstance(val.get("trigger"), dict):
            tr = val["trigger"]
            if tr.get("type") == "item":
                removed = [f for f in ("auranames", "realSpellName", "spellName", "spellIds")
                           if f in tr]
                for f in removed:
                    tr.pop(f)
                if removed:
                    report.append(f'{aura["id"]}: t{key} item trigger — stripped residue {removed}')


def fix_swing_timer_proc(aura, report):
    """t3 tracked SoD Power Surge (415105) by exact id to color the bar red
    during the haste proc. TBC equivalent proc is Flurry — track by name
    (rank-agnostic); the barColor condition on trigger 3 keeps working."""
    if not aura["id"].endswith("Swing Timer [MH]"):
        return
    tr = aura["triggers"]["3"]["trigger"]
    assert tr.get("auraspellids") == ["415105"], "unexpected Swing Timer t3 shape"
    tr["auraspellids"] = []
    tr["useExactSpellId"] = False
    tr["useName"] = True
    tr["auranames"] = ["Flurry"]
    report.append(f'{aura["id"]}: t3 haste-proc repointed Power Surge(SoD) -> Flurry by name')


def fix_load(aura, report):
    load = aura.get("load", {})
    # vacuous SoD gates: not_spellknown on an id that no longer exists
    nk = load.get("not_spellknown")
    if load.get("use_not_spellknown") and isinstance(nk, (int, float)) and nk >= 400000:
        load["use_not_spellknown"] = False
        load.pop("not_spellknown", None)
        report.append(f'{aura["id"]}: stripped vacuous SoD not_spellknown={int(nk)} gate')
    sk = load.get("spellknown")
    if load.get("use_spellknown") and isinstance(sk, (int, float)) and sk >= 400000:
        # would never load in TBC; REPOINT should have caught mapped ones
        report.append(f'{aura["id"]}: WARNING spellknown={int(sk)} still SoD — aura will never load')


def main() -> int:
    payload = json.loads(SRC.read_text())
    auras = [payload["d"]] + list(payload.get("c") or [])
    by_id = {a["id"]: a for a in auras}

    # expand DROP to full subtrees
    drop = set()
    def mark(aura_id):
        drop.add(aura_id)
        for child in (by_id.get(aura_id, {}).get("controlledChildren") or []):
            mark(child)
    for aura_id in DROP:
        if aura_id in by_id:
            mark(aura_id)

    report = [f"dropped ({len(drop)}): " + ", ".join(sorted(drop))]
    kept = []
    for aura in auras:
        if aura["id"] in drop:
            continue
        aura = repoint_tree(aura)          # spell ids everywhere (triggers + loads)
        aura.pop("uid", None)
        aura.pop("wagoID", None)
        fix_load(aura, report)
        clean_item_trigger_residue(aura, report)
        fix_swing_timer_proc(aura, report)
        old_id = aura["id"]
        aura["id"] = rename(old_id)
        if aura.get("parent"):
            if aura["parent"] in drop:
                raise SystemExit(f"{old_id}: parent {aura['parent']} was dropped — inconsistent DROP set")
            aura["parent"] = rename(aura["parent"])
        if aura.get("controlledChildren") is not None:
            aura["controlledChildren"] = [rename(c) for c in aura["controlledChildren"] if c not in drop]
        aff = aura.get("anchorFrameFrame")
        if isinstance(aff, str) and aff.startswith("WeakAuras:"):
            target = aff[len("WeakAuras:"):]
            if target in drop:
                raise SystemExit(f"{old_id}: anchored to dropped aura {target}")
            if target in by_id:
                aura["anchorFrameFrame"] = "WeakAuras:" + rename(target)
                report.append(f'{aura["id"]}: re-anchored to {rename(target)}')
        kept.append(aura)

    root = kept[0]
    assert root["id"] == ROOT_NEW, "first aura must be the renamed root"
    root.pop("parent", None)
    out_payload = {"m": "d", "v": 2000, "s": payload.get("s", "5.21.8"),
                   "d": root, "c": kept[1:]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out_payload, indent=2, sort_keys=True) + "\n")
    for line in report:
        print(line)
    print(f"\n{len(kept)} auras -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
