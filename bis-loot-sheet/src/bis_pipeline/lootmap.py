"""Map WCL encounters to their loot tables via the cmangos DB.

Creature matching is by encounter name against creature_template (only rows
with a lootid), with per-encounter overrides where the loot-carrying creature
differs from the encounter name (council fights, multi-phase bosses).

Loot expansion follows the mangos convention: `mincountOrRef < 0` points into
reference_loot_template at entry = -mincountOrRef (expanded recursively).

Kept items: Quality >= 4 (epics incl. tier tokens), or Quality 3 weapons and
armor. This drops Badges of Justice, quest objectives, and holiday junk.
"""

import json
import logging
import sqlite3

from .config import META_DIR, ZONES
from .enrich import CMANGOS_DB

log = logging.getLogger(__name__)

# encounter id -> creature entries carrying the loot, where name-match fails.
CREATURE_OVERRIDES: dict[int, list[int]] = {
    606: [23420],  # Reliquary of Souls -> Essence of Anger (final essence)
    # Illidari Council: items ride on Zerevor (ref 36135), the T6 legs token
    # group (ref 36136) on the other three - Gathios covers it once.
    608: [22949, 22950],
    # WCL names ZA's final boss "Daakara" (Cataclysm-era); in 2.4.3 the boss
    # and loot are Zul'jin.
    1194: [23863],
    # Sunwell: loot rides on the fight's second body.
    724: [24892],  # Kalecgos -> Sathrovarr the Corruptor
    727: [25165, 25166],  # Eredar Twins -> Sacrolash + Alythess
    728: [25840],  # M'uru -> Entropius
}


BADGE_OF_JUSTICE = 29434  # epic-quality currency, drops everywhere - not loot-sheet material


def _keep(quality: int, item_class: int, entry: int = 0) -> bool:
    # class 3 = gems, class 9 = recipes - drop from raid trash but aren't gear
    if item_class in (3, 9) or entry == BADGE_OF_JUSTICE:
        return False
    return quality >= 4 or (quality == 3 and item_class in (2, 4))


def _expand_loot(con: sqlite3.Connection, loot_ids: list[int]) -> set[int]:
    items: set[int] = set()
    seen_refs: set[int] = set()

    def walk(table: str, entries: list[int]) -> None:
        if not entries:
            return
        placeholders = ",".join("?" * len(entries))
        rows = con.execute(
            f"SELECT item, mincountOrRef FROM {table} WHERE entry IN ({placeholders})",
            entries,
        ).fetchall()
        refs = []
        for item, mincount_or_ref in rows:
            if mincount_or_ref < 0:
                ref = -mincount_or_ref
                if ref not in seen_refs:
                    seen_refs.add(ref)
                    refs.append(ref)
            else:
                items.add(item)
        walk("reference_loot_template", refs)

    walk("creature_loot_template", loot_ids)
    return items


def build_lootmap(zone_tag: str) -> dict:
    zone = ZONES[zone_tag]
    encounters = json.loads((META_DIR / f"encounters-{zone['zone_id']}.json").read_text())
    con = sqlite3.connect(CMANGOS_DB)

    result: dict[str, dict] = {}
    for enc in encounters:
        if enc["id"] in CREATURE_OVERRIDES:
            creatures = CREATURE_OVERRIDES[enc["id"]]
        else:
            creatures = [
                row[0]
                for row in con.execute(
                    "SELECT lootid FROM creature_template WHERE name = ? AND lootid > 0",
                    (enc["name"],),
                )
            ]
        if not creatures:
            log.warning("no loot creature found for encounter %d %s", enc["id"], enc["name"])
            continue
        candidates = _expand_loot(con, creatures)
        kept = []
        if candidates:
            placeholders = ",".join("?" * len(candidates))
            kept = [
                entry
                for entry, quality, item_class in con.execute(
                    f"SELECT entry, Quality, class FROM item_template "
                    f"WHERE entry IN ({placeholders})",
                    sorted(candidates),
                )
                if _keep(quality, item_class, entry)
            ]
        result[str(enc["id"])] = {"name": enc["name"], "items": sorted(kept)}
        log.info("lootmap %s: %d items", enc["name"], len(kept))

    boss_items = {i for enc in result.values() for i in enc["items"]}
    result.update(build_trash(zone_tag, con, boss_items))

    out_path = META_DIR / f"lootmap-{zone_tag}.json"
    out_path.write_text(json.dumps(result, indent=1))
    return result


# Raid map ids per zone, for the per-raid "Trash" pseudo-encounters
# (pseudo id = 900000 + map id; the app maps these to raid names).
RAID_MAPS: dict[str, list[int]] = {
    "karazhan": [532],
    "gruul-magtheridon": [565, 544],
    "ssc-tk": [548, 550],
    "bt-hyjal": [534, 564],
    "zul-aman": [568],
    "sunwell": [580],
}

# Hyjal trash arrives in scripted waves with no static spawns; name the wave
# roster explicitly (their creature_templates carry the trash loot ref).
TRASH_EXTRA_CREATURES: dict[int, list[str]] = {
    534: [
        "Ghoul",
        "Crypt Fiend",
        "Abomination",
        "Necromancer",
        "Banshee",
        "Gargoyle",
        "Frost Wyrm",
        "Giant Infernal",
        "Fel Stalker",
    ],
}

# A raid-trash loot reference is used (almost) exclusively by this raid's
# creatures; a global world-drop table's users are scattered everywhere.
LOCAL_REF_MIN_SHARE = 0.5


def build_trash(zone_tag: str, con: sqlite3.Connection, boss_items: set[int]) -> dict[str, dict]:
    """Per-raid-map Trash pseudo-encounters from non-boss creature loot."""
    result: dict[str, dict] = {}
    for map_id in RAID_MAPS.get(zone_tag, []):
        lootids = {
            row[0]
            for row in con.execute(
                "SELECT DISTINCT ct.lootid FROM creature c "
                "JOIN creature_template ct ON ct.entry = c.id "
                "WHERE c.map = ? AND ct.lootid > 0",
                (map_id,),
            )
        }
        for name in TRASH_EXTRA_CREATURES.get(map_id, []):
            lootids.update(
                row[0]
                for row in con.execute(
                    "SELECT lootid FROM creature_template WHERE name = ? AND lootid > 0",
                    (name,),
                )
            )
        items: set[int] = set()
        for lootid in lootids:
            for item, mref in con.execute(
                "SELECT item, mincountOrRef FROM creature_loot_template WHERE entry = ?",
                (lootid,),
            ):
                if mref >= 0:
                    items.add(item)
                    continue
                ref = -mref
                users = {
                    row[0]
                    for row in con.execute(
                        "SELECT DISTINCT entry FROM creature_loot_template WHERE mincountOrRef = ?",
                        (-ref,),
                    )
                }
                local_share = len(users & lootids) / max(1, len(users))
                if local_share < LOCAL_REF_MIN_SHARE:
                    continue  # global world-drop table
                items.update(
                    row[0]
                    for row in con.execute(
                        "SELECT item FROM reference_loot_template WHERE entry = ?", (ref,)
                    )
                )
        kept: list[int] = []
        if items:
            placeholders = ",".join("?" * len(items))
            kept = [
                entry
                for entry, quality, item_class in con.execute(
                    f"SELECT entry, Quality, class FROM item_template "
                    f"WHERE entry IN ({placeholders})",
                    sorted(items),
                )
                if _keep(quality, item_class, entry) and entry not in boss_items
            ]
        result[str(900000 + map_id)] = {"name": "Trash", "items": sorted(kept)}
        log.info("trash lootmap map %d (%s): %d items", map_id, zone_tag, len(kept))
    return result


def load_lootmap(zone_tag: str) -> dict | None:
    path = META_DIR / f"lootmap-{zone_tag}.json"
    return json.loads(path.read_text()) if path.exists() else None


def later_phase_items(tag: str) -> set[int]:
    """All raid-dropped item ids from zones of a LATER anniversary phase.

    Used to purge poisoned ranking rows: a player wearing any of these was
    logged after the next tier released and does not represent this phase.
    Accepts a phase tag or zone tag.
    """
    from .config import phase_number, resolve_phase

    own_phase = phase_number(resolve_phase(tag))
    ids: set[int] = set()
    for other_tag, other in ZONES.items():
        if other["anniversary_phase"] > own_phase:
            other_map = load_lootmap(other_tag) or build_lootmap(other_tag)
            for enc in other_map.values():
                ids.update(enc["items"])

    # Raid lootmaps miss patch-gated non-raid items (badge vendor, crafted).
    # Wowhead's per-item phase tags cover those - see item_phases.py.
    from .item_phases import (
        build_observed_clearance,
        effective_phase,
        load_clearance,
        load_item_phases,
    )

    phases = load_item_phases()
    if phases is None:
        log.warning(
            "item phase cache missing - run `bis-pipeline item-phases`; "
            "poison set covers raid drops only"
        )
    else:
        clearance = load_clearance()
        if clearance is None:
            clearance = build_observed_clearance()
        for i in phases:
            eff = effective_phase(i, phases, clearance)
            if eff and eff > own_phase:
                ids.add(int(i))
    return ids


# Tier token name grammar: "<SlotWord> of the <Fallen|Vanquished|Forgotten> …".
TOKEN_SLOT_TYPES = {
    "Helm": (1,),
    "Pauldrons": (3,),
    "Chestguard": (5, 20),
    "Gauntlets": (10,),
    "Gloves": (10,),
    "Leggings": (7,),
    "Bracers": (9,),
    "Belt": (6,),
    "Boots": (8,),
}
TOKEN_TIER_ILVL = {"Fallen": 120, "Vanquished": 133, "Forgotten": (146, 154)}


def build_token_pieces() -> dict[str, list[int]]:
    """token item id -> redeemable tier piece ids (all class/role variants).

    Derived, not hardcoded: the token's own AllowableClass gives the classes;
    the slot word gives the inventory type; the tier word gives the piece
    item level. Pieces are the class-restricted set items matching all three.
    """
    from .enrich import CLASS_MASKS

    con = sqlite3.connect(CMANGOS_DB)
    con.row_factory = sqlite3.Row
    tokens = con.execute(
        "SELECT entry, name, AllowableClass FROM item_template "
        "WHERE class = 15 AND Quality >= 4 AND ("
        "name LIKE '%of the Fallen %' OR name LIKE '%of the Vanquished %' "
        "OR name LIKE '%of the Forgotten %')"
    ).fetchall()
    result: dict[str, list[int]] = {}
    for tok in tokens:
        slot_word = tok["name"].split(" of the ")[0].split()[-1]
        tier_word = tok["name"].split(" of the ")[1].split()[0]
        inv_types = TOKEN_SLOT_TYPES.get(slot_word)
        ilvls = TOKEN_TIER_ILVL.get(tier_word)
        if not inv_types or not ilvls:
            log.warning("token %s: unparsed slot/tier", tok["name"])
            continue
        if isinstance(ilvls, int):
            ilvls = (ilvls,)
        class_masks = [m for m, _ in CLASS_MASKS.items() if tok["AllowableClass"] & m]
        pieces: list[int] = []
        for mask in class_masks:
            pieces.extend(
                row[0]
                for row in con.execute(
                    f"SELECT entry FROM item_template WHERE Quality = 4 AND itemset != 0 "
                    f"AND InventoryType IN ({','.join(map(str, inv_types))}) "
                    f"AND ItemLevel IN ({','.join(map(str, ilvls))}) "
                    f"AND name NOT LIKE '%Gladiator%' "  # arena sets share ilvl/shape
                    f"AND AllowableClass = ?",
                    (mask,),
                )
            )
        result[str(tok["entry"])] = sorted(pieces)
        if not pieces:
            log.warning("token %s (%d): no pieces resolved", tok["name"], tok["entry"])
    out = META_DIR / "token_pieces.json"
    out.write_text(json.dumps(result, indent=1))
    log.info("token pieces: %d tokens -> %s", len(result), out)
    return result
