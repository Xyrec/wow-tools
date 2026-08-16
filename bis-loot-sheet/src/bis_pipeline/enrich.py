"""Enrich aggregated distributions with item facts from the cmangos TBC DB.

Restructures the aggregated JSON: item metadata moves to a single top-level
`items` table (keyed by id) and spec slot entries slim down to id/count/pct.
Adds, per item: canonical 2.4.3 name, quality, item level, inventory type,
armor/weapon subclass, allowable classes, unique and unique-equipped flags.

Item ids that don't resolve in the DB (e.g. Anniversary-era pollution in a
classic partition) are logged and dropped.
"""

import json
import logging
import re
import sqlite3
from pathlib import Path

from .aggregate import AGGREGATED_DIR
from .config import META_DIR, PROJECT_ROOT

log = logging.getLogger(__name__)

ENRICHED_DIR = AGGREGATED_DIR.parent / "enriched"
CMANGOS_DB = PROJECT_ROOT.parent / "sources" / "cmangos-tbc-db" / "tbcmangos.sqlite"

ITEM_FLAG_UNIQUE_EQUIPPED = 0x00080000

CLASS_MASKS = {
    1: "Warrior",
    2: "Paladin",
    4: "Hunter",
    8: "Rogue",
    16: "Priest",
    64: "Shaman",
    128: "Mage",
    256: "Warlock",
    1024: "Druid",
}

INVENTORY_TYPES = {
    1: "head",
    2: "neck",
    3: "shoulder",
    4: "shirt",
    5: "chest",
    6: "waist",
    7: "legs",
    8: "feet",
    9: "wrist",
    10: "hands",
    11: "finger",
    12: "trinket",
    13: "one_hand",
    14: "shield",
    15: "ranged",
    16: "back",
    17: "two_hand",
    20: "chest",
    21: "main_hand",
    22: "off_hand_weapon",
    23: "held_off_hand",
    25: "thrown",
    26: "ranged",
    28: "relic",
}

ARMOR_SUBCLASSES = {1: "cloth", 2: "leather", 3: "mail", 4: "plate", 6: "shield"}

ITEM_COLUMNS = (
    "entry, name, Quality, ItemLevel, InventoryType, AllowableClass, "
    "Flags, maxcount, class, subclass, itemset, " + ", ".join(f"stat_type{i}" for i in range(1, 11))
)

ITEM_MOD_RESILIENCE = 35
# Honor/arena gear naming, for PvP pieces that predate resilience.
PVP_NAME_RE = re.compile(
    r"gladiator's|\bmarshal's|\bgeneral's|high warlord's|veteran's|vindicator's|sergeant's",
    re.IGNORECASE,
)


def _is_pvp(row: sqlite3.Row) -> bool:
    stats = (row[f"stat_type{i}"] for i in range(1, 11))
    return ITEM_MOD_RESILIENCE in stats or bool(PVP_NAME_RE.search(row["name"]))


def _allowable_classes(mask: int) -> list[str] | None:
    """None means usable by all classes."""
    if mask in (-1, 0, 32767):
        return None
    return [name for bit, name in CLASS_MASKS.items() if mask & bit]


def _item_facts(row: sqlite3.Row) -> dict:
    facts = {
        "name": row["name"],
        "quality": row["Quality"],
        "itemLevel": row["ItemLevel"],
        "slot": INVENTORY_TYPES.get(row["InventoryType"], f"type-{row['InventoryType']}"),
        "unique": row["maxcount"] == 1,
        "uniqueEquipped": bool(row["Flags"] & ITEM_FLAG_UNIQUE_EQUIPPED),
    }
    if row["class"] == 4 and row["subclass"] in ARMOR_SUBCLASSES:
        facts["armorType"] = ARMOR_SUBCLASSES[row["subclass"]]
    if row["itemset"]:
        facts["setId"] = row["itemset"]
    if _is_pvp(row):
        facts["pvp"] = True
    if row["class"] == 15 and row["Quality"] >= 4:
        facts["token"] = True
    allowable = _allowable_classes(row["AllowableClass"])
    if allowable:
        facts["allowableClasses"] = allowable
    return facts


def _fetch_icons(item_ids: list[int]) -> dict[int, str]:
    """Icon names for items absent from gear data, via WCL gameData (cached)."""
    cache_file = META_DIR / "icons.json"
    cache: dict[str, str] = json.loads(cache_file.read_text()) if cache_file.exists() else {}

    missing = [i for i in item_ids if str(i) not in cache]
    if missing:
        from .client import WCLClient

        client = WCLClient()
        for chunk_start in range(0, len(missing), 50):
            chunk = missing[chunk_start : chunk_start + 50]
            aliases = " ".join(f"i{i}: item(id: {i}) {{ icon }}" for i in chunk)
            data = client.query(f"gameData {{ {aliases} }}")
            for i in chunk:
                node = data["gameData"].get(f"i{i}")
                if node and node.get("icon"):
                    cache[str(i)] = node["icon"]
        cache_file.write_text(json.dumps(cache, indent=1))
        log.info("fetched %d icons from WCL gameData", len(missing))

    return {i: cache[str(i)] for i in item_ids if str(i) in cache}


def enrich_zone(zone_tag: str) -> Path:
    src = AGGREGATED_DIR / f"{zone_tag}.json"
    data = json.loads(src.read_text())

    ids: set[int] = set()
    for spec_data in data["specs"].values():
        for band in spec_data["bands"].values():
            for entries in band["slots"].values():
                ids.update(e["id"] for e in entries)

    con = sqlite3.connect(CMANGOS_DB)
    con.row_factory = sqlite3.Row
    placeholders = ",".join("?" * len(ids))
    rows = con.execute(
        f"SELECT {ITEM_COLUMNS} FROM item_template WHERE entry IN ({placeholders})",
        sorted(ids),
    ).fetchall()
    items = {row["entry"]: _item_facts(row) for row in rows}

    dropped = sorted(ids - set(items))
    for item_id in dropped:
        log.warning("dropping item %d: not in cmangos TBC DB (non-TBC pollution?)", item_id)

    specs = {}
    for spec_key, spec_data in data["specs"].items():
        bands = {}
        for band_key, band in spec_data["bands"].items():
            slots = {}
            for slot, entries in band["slots"].items():
                kept = [
                    {"id": e["id"], "count": e["count"], "pct": e["pct"]}
                    for e in entries
                    if e["id"] in items
                ]
                # Preserve WCL's icon (cmangos stores display ids, not icon
                # names) and note WCL names that differ from 2.4.3 canonical.
                for e in entries:
                    if e["id"] in items:
                        items[e["id"]].setdefault("icon", e["icon"])
                        if e["name"] != items[e["id"]]["name"]:
                            items[e["id"]].setdefault("wclName", e["name"])
                slots[slot] = kept
            bands[band_key] = {"sampleSize": band["sampleSize"], "slots": slots}
        specs[spec_key] = {"bands": bands}

    from .lootmap import build_lootmap, load_lootmap

    lootmap = build_lootmap(zone_tag)
    encounters = {eid: e["name"] for eid, e in lootmap.items()}

    # Drop-only items (tier tokens above all — nobody *wears* a token, but
    # they ARE what the loot council assigns) still need item facts.
    drop_only = {
        item_id for enc in lootmap.values() for item_id in enc["items"] if item_id not in items
    }
    if drop_only:
        placeholders = ",".join("?" * len(drop_only))
        for row in con.execute(
            f"SELECT {ITEM_COLUMNS} FROM item_template WHERE entry IN ({placeholders})",
            sorted(drop_only),
        ):
            items[row["entry"]] = {**_item_facts(row), "dropOnly": True}
        for item_id, icon in _fetch_icons(sorted(drop_only)).items():
            items[item_id]["icon"] = icon

    for eid, enc in lootmap.items():
        for item_id in enc["items"]:
            if item_id in items:
                items[item_id].setdefault("sources", []).append(int(eid))

    # Zones sharing a partition can leak later-phase gear into the worn data
    # (ZA inside "P3.5 & P4"). Flag anything dropping in a later-phase raid so
    # the app and prio logic can mark it unobtainable in this Anniversary phase.
    from .config import ZONES

    own_phase = ZONES[zone_tag]["anniversary_phase"]
    for other_tag, other in ZONES.items():
        if other["anniversary_phase"] <= own_phase:
            continue
        other_map = load_lootmap(other_tag) or build_lootmap(other_tag)
        for enc in other_map.values():
            for item_id in enc["items"]:
                if item_id in items:
                    items[item_id]["laterPhase"] = other_tag

    result = {k: v for k, v in data.items() if k != "specs"}
    result["encounters"] = encounters
    result["items"] = items
    result["specs"] = specs

    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ENRICHED_DIR / f"{zone_tag}.json"
    out_path.write_text(json.dumps(result, indent=1))

    # Keep the web app's data in sync automatically.
    app_data = PROJECT_ROOT / "app" / "src" / "data"
    if app_data.is_dir():
        (app_data / f"{zone_tag}.json").write_text(json.dumps(result))
        log.info("synced to app/src/data/%s.json", zone_tag)
    log.info(
        "enriched %s: %d items (%d dropped as non-TBC) -> %s",
        zone_tag,
        len(items),
        len(dropped),
        out_path,
    )
    return out_path
