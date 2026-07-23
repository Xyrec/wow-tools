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


def _alpha_or_checks(aura):
    """The OR-combined checks list of the group-wide alpha-dim condition."""
    for cond in aura.get("conditions", []):
        chk = cond.get("check", {})
        if (chk.get("variable") == "OR"
                and any(ch.get("property") == "alpha" for ch in cond.get("changes", []))):
            return chk.setdefault("checks", [])
    return None


def tweak_mana_bar_alpha(aura, report):
    """OOC dimming only at FULL mana: stay bright while mana is regening so a
    non-full bar is easy to spot (t1 is the Power trigger; percentpower is a
    stored state value)."""
    checks = _alpha_or_checks(aura)
    if checks is not None and not any(c.get("variable") == "percentpower" for c in checks):
        checks.append({"trigger": 1, "variable": "percentpower", "op": "<", "value": "100"})
        report.append(f'{aura["id"]}: alpha condition also brightens below 100% mana')


def tweak_mana_tick_alpha(aura, report):
    """Match the Mana Bar: the tick spark's states only exist while mana is
    regening/spent, so brighten whenever its trigger is active."""
    checks = _alpha_or_checks(aura)
    if checks is not None and not any(c.get("variable") == "show" for c in checks):
        checks.append({"trigger": 1, "variable": "show", "value": 1})
        report.append(f'{aura["id"]}: alpha condition also brightens while tick active')


# per-aura behavior tweaks applied AFTER rename + port_live_tweaks, so they
# survive rebuilds (ported donor conditions would otherwise win)
LOCAL_TWEAKS = {
    "Xyrec Shaman - Mana Bar": tweak_mana_bar_alpha,
    "Xyrec Shaman - Mana Tick": tweak_mana_tick_alpha,
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


LIVE_SRC = REPO / "data" / "auras" / "mine" / "sabimaru-live.json"

# fields that carry the properly-migrated logic — NEVER ported from live
LOGIC_KEEP = {"id", "uid", "parent", "controlledChildren", "wagoID", "triggers", "load"}

# the user's group-wide "dim to 0.3 unless (attackable target OR in combat)" tweak
GLOBAL_ALPHA_CONDITION = {
    "changes": [{"property": "alpha", "value": 1}],
    "check": {"trigger": -2, "variable": "OR",
              "checks": [{"trigger": -1, "value": 1, "variable": "attackabletarget"},
                         {"trigger": -1, "value": 1, "variable": "incombat"}]},
}

LIVE_ID_MAP = {  # old-id -> live-id where they differ
    "Shaman - Flame Shock [Dps]": "Shaman - Flame Shock",
}


def trigger_keys(aura):
    t = aura.get("triggers", {})
    if isinstance(t, list):
        return {str(i + 1) for i in range(len(t))}
    return {str(k) for k in t if str(k).isdigit()}


def port_live_tweaks(aura, old_id, live_by_id, report):
    """Adopt the live group's presentation (the user's accumulated look) while
    keeping this build's migrated logic. Conditions port only when the trigger
    layout matches, since they reference triggers by number."""
    live = live_by_id.get(LIVE_ID_MAP.get(old_id, old_id))
    if live is None:
        # restored aura with no live counterpart: apply the group-wide alpha pattern
        aura["alpha"] = 0.3
        conds = aura.setdefault("conditions", [])
        if not any("attackabletarget" in json.dumps(c) for c in conds):
            conds.append(json.loads(json.dumps(GLOBAL_ALPHA_CONDITION)))
        report.append(f'{aura["id"]}: no live counterpart — applied group alpha pattern')
        return
    ported = 0
    for key, value in live.items():
        if key in LOGIC_KEEP or key == "conditions":
            continue
        if json.dumps(aura.get(key), sort_keys=True) != json.dumps(value, sort_keys=True):
            aura[key] = json.loads(json.dumps(value))
            ported += 1
    if "conditions" in live:
        if trigger_keys(aura) == trigger_keys(live):
            aura["conditions"] = json.loads(json.dumps(live["conditions"]))
        else:
            report.append(f'{aura["id"]}: trigger layout differs from live — conditions NOT ported, review')
    if ported:
        report.append(f'{aura["id"]}: ported {ported} presentation fields from live')


# pixel-valued fields that must be multiplied when baking the root scale
BAKE_REGION_FIELDS = ["width", "height", "xOffset", "yOffset", "borderSize", "borderOffset",
                      "borderInset", "space", "stagger", "radius", "rowSpace", "columnSpace",
                      "sparkWidth", "sparkHeight", "sparkOffsetX", "sparkOffsetY"]
BAKE_SUBREGION_FIELDS = ["anchorXOffset", "anchorYOffset", "border_offset", "border_size",
                         "text_anchorXOffset", "text_anchorYOffset", "text_fixedWidth",
                         "text_fontSize", "text_shadowXOffset", "text_shadowYOffset"]


def bake_root_scale(auras, report):
    """Multiply all pixel dimensions by the root's scale and set scale to 1, so
    borders/sizes land on the integer pixel grid (kills the 1px/2px flicker a
    fractional scale transform causes). WoW offsets are measured in the frame's
    own scale, so the root's screen offsets are multiplied as well."""
    root = auras[0]
    factor = root.get("scale") or 1
    if factor == 1:
        return
    def mul(v):
        return int(round(v * factor))
    for aura in auras:
        for f in BAKE_REGION_FIELDS:
            if isinstance(aura.get(f), (int, float)) and not isinstance(aura.get(f), bool):
                aura[f] = mul(aura[f])
        for sub in (aura.get("subRegions") or []):
            for f in BAKE_SUBREGION_FIELDS:
                if isinstance(sub.get(f), (int, float)) and not isinstance(sub.get(f), bool):
                    sub[f] = mul(sub[f])
        for cond in (aura.get("conditions") or []):
            for ch in (cond.get("changes") or []):
                prop = str(ch.get("property") or "")
                if isinstance(ch.get("value"), (int, float)) and not isinstance(ch.get("value"), bool) \
                        and (prop.endswith("text_fontSize") or prop in ("width", "height")):
                    ch["value"] = mul(ch["value"])
    root["scale"] = 1
    report.append(f"baked root scale x{factor} into pixel fields (scale reset to 1)")


def main() -> int:
    payload = json.loads(SRC.read_text())
    live_payload = json.loads(LIVE_SRC.read_text())
    live_by_id = {a["id"]: a for a in [live_payload["d"]] + list(live_payload.get("c") or [])}
    live_by_id["Sabimaru - Shaman Classic [SoD]"] = live_payload["d"]
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
        port_live_tweaks(aura, old_id, live_by_id, report)
        aura["id"] = rename(old_id)
        tweak = LOCAL_TWEAKS.get(aura["id"])
        if tweak:
            tweak(aura, report)
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
    if "--bake-scale" in sys.argv:
        # opt-in: integer-pixel baking caused awkward overlaps in the dynamic
        # groups (rounding shifted child layout); default stays scale=1.5
        bake_root_scale(kept, report)
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
