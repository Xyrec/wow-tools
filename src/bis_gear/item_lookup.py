"""Look up TBC item stats from the cmangos SQLite database.

Usage:
    uv run item-lookup 29183          # single item
    uv run item-lookup 29183 28503    # multiple items
    uv run item-lookup --compare 29183 28503   # side-by-side with diff
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from functools import cache
from pathlib import Path

SOURCES_DIR = Path(__file__).resolve().parents[2] / "sources" / "cmangos-tbc-db"
DB_PATH = SOURCES_DIR / "tbcmangos.sqlite"
AURA_DEFINES_PATH = SOURCES_DIR / "src" / "SpellAuraDefines.h"

STAT_TYPE_NAMES: dict[int, str] = {
    0: "(none)",
    1: "Health",
    3: "Agility",
    4: "Strength",
    5: "Intellect",
    6: "Spirit",
    7: "Stamina",
    12: "Defense Rating",
    13: "Dodge Rating",
    14: "Parry Rating",
    15: "Block Rating",
    16: "Melee Hit Rating",
    17: "Ranged Hit Rating",
    18: "Spell Hit Rating",
    19: "Melee Crit Rating",
    20: "Ranged Crit Rating",
    21: "Spell Crit Rating",
    31: "Hit Rating",
    32: "Crit Rating",
    35: "Resilience",
    36: "Haste Rating",
    37: "Expertise Rating",
    38: "Attack Power",
    39: "Ranged Attack Power",
    41: "+Healing (deprecated WotLK)",
    42: "+Spell Damage (deprecated WotLK)",
    43: "MP5",
    44: "Armor Penetration",
    45: "Spell Power",
    46: "Health per 5",
    47: "Spell Penetration",
}

INVENTORY_TYPES: dict[int, str] = {
    0: "Non-equippable",
    1: "Head",
    2: "Neck",
    3: "Shoulder",
    4: "Shirt",
    5: "Chest",
    6: "Waist",
    7: "Legs",
    8: "Feet",
    9: "Wrist",
    10: "Hands",
    11: "Finger",
    12: "Trinket",
    13: "One-Hand",
    14: "Shield",
    15: "Ranged",
    16: "Back",
    17: "Two-Hand",
    18: "Bag",
    20: "Chest (robe)",
    21: "Main Hand",
    22: "Off Hand",
    23: "Held In Off-Hand",
    24: "Ammo",
    25: "Thrown",
    26: "Ranged (gun/wand)",
    28: "Relic",
}

QUALITY_NAMES: dict[int, str] = {
    0: "Poor",
    1: "Common",
    2: "Uncommon",
    3: "Rare",
    4: "Epic",
    5: "Legendary",
}

ITEM_CLASS_NAMES: dict[int, str] = {
    0: "Consumable",
    1: "Container",
    2: "Weapon",
    4: "Armor",
    7: "Trade Goods",
    9: "Recipe",
    12: "Quest",
    15: "Miscellaneous",
}

ARMOR_SUBCLASS: dict[int, str] = {
    0: "Misc",
    1: "Cloth",
    2: "Leather",
    3: "Mail",
    4: "Plate",
    5: "Buckler (obsolete)",
    6: "Shield",
    7: "Libram",
    8: "Idol",
    9: "Totem",
}

SOCKET_COLORS: dict[int, str] = {
    1: "Meta",
    2: "Red",
    4: "Yellow",
    8: "Blue",
}


@cache
def _load_aura_names() -> dict[int, str]:
    """Parse AuraType enum from SpellAuraDefines.h into {id: friendly_name}."""
    text = AURA_DEFINES_PATH.read_text()
    match = re.search(r"enum AuraType\s*\{(.*?)\}", text, re.DOTALL)
    if not match:
        return {}
    result: dict[int, str] = {}
    for name, val in re.findall(r"(SPELL_AURA_\w+)\s*=\s*(\d+)", match.group(1)):
        friendly = name.removeprefix("SPELL_AURA_").replace("_", " ").title()
        result[int(val)] = friendly
    return result


def _get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"Error: TBC database not found at {DB_PATH}", file=sys.stderr)
        print(
            "Download from: https://github.com/cmangos/tbc-db/releases", file=sys.stderr
        )
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


def _decode_spell_effects(
    conn: sqlite3.Connection, spell_id: int
) -> list[tuple[str, int]]:
    """Decode a spell_template entry into (stat_name, value) pairs."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM spell_template WHERE Id=?", (spell_id,))
    row = cur.fetchone()
    if not row:
        return []
    cols = [c[0] for c in cur.description]
    spell = dict(zip(cols, row))

    effects: list[tuple[str, int]] = []
    for i in range(1, 4):
        aura = spell.get(f"EffectApplyAuraName{i}", 0)
        base = spell.get(f"EffectBasePoints{i}", 0)
        if aura == 0 or base == 0:
            continue
        value = base + 1  # cmangos stores base-1

        aura_names = _load_aura_names()
        name = aura_names.get(aura, spell.get("SpellName", f"Aura {aura}"))
        effects.append((name, value))
    return effects


def lookup_item(conn: sqlite3.Connection, item_id: int) -> dict | None:
    """Look up an item and return a structured dict of its stats."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM item_template WHERE entry=?", (item_id,))
    row = cur.fetchone()
    if not row:
        return None
    cols = [c[0] for c in cur.description]
    item = dict(zip(cols, row))

    # Basic info
    result: dict = {
        "id": item_id,
        "name": item["name"],
        "quality": QUALITY_NAMES.get(item["Quality"], str(item["Quality"])),
        "item_level": item["ItemLevel"],
        "required_level": item["RequiredLevel"],
        "slot": INVENTORY_TYPES.get(item["InventoryType"], str(item["InventoryType"])),
        "armor": item["armor"],
        "stats": {},
    }

    # Item type
    item_class = item["class"]
    if item_class == 4:  # Armor
        result["type"] = ARMOR_SUBCLASS.get(item["subclass"], str(item["subclass"]))
    elif item_class == 2:  # Weapon
        result["type"] = "Weapon"

    # Stat columns
    for i in range(1, 11):
        st = item[f"stat_type{i}"]
        sv = item[f"stat_value{i}"]
        if st != 0 and sv != 0:
            name = STAT_TYPE_NAMES.get(st, f"Unknown({st})")
            result["stats"][name] = sv

    # Sockets
    sockets: list[str] = []
    for i in range(1, 4):
        color_id = item[f"socketColor_{i}"]
        if color_id:
            sockets.append(SOCKET_COLORS.get(color_id, f"Unknown({color_id})"))
    if sockets:
        result["sockets"] = sockets
    bonus_id = item["socketBonus"]
    if bonus_id:
        result["socket_bonus_id"] = bonus_id

    # Spell effects (where +healing, +spell damage, mp5 often live)
    for i in range(1, 6):
        spell_id = item[f"spellid_{i}"]
        trigger = item[f"spelltrigger_{i}"]
        if spell_id != 0 and trigger == 1:  # trigger=1 means "Equip:"
            effects = _decode_spell_effects(conn, spell_id)
            for stat_name, value in effects:
                if stat_name in result["stats"]:
                    result["stats"][stat_name] += value
                else:
                    result["stats"][stat_name] = value

    # Collapse equal Mod Healing Done / Mod Damage Done into a single stat
    healing = result["stats"].get("Mod Healing Done")
    damage = result["stats"].get("Mod Damage Done")
    if healing is not None and damage is not None and healing == damage:
        del result["stats"]["Mod Healing Done"]
        del result["stats"]["Mod Damage Done"]
        result["stats"]["Spell Damage and Healing"] = healing

    return result


def print_item(item: dict) -> None:
    """Print a single item's stats."""
    qual = item["quality"]
    print(f"  {item['name']}  (ilvl {item['item_level']} {qual})")
    print(
        f"  ID: {item['id']}  |  Slot: {item['slot']}  |  Type: {item.get('type', '-')}"
    )
    if item["armor"]:
        print(f"  Armor: {item['armor']}")
    if sockets := item.get("sockets"):
        print(f"  Sockets: {', '.join(sockets)}")
    print("  Stats:")
    for stat, val in item["stats"].items():
        print(f"    {stat}: +{val}")
    print()


def print_compare(items: list[dict]) -> None:
    """Print a side-by-side comparison table with diff column."""
    all_stats: list[str] = ["Armor"]
    for item in items:
        for s in item["stats"]:
            if s not in all_stats:
                all_stats.append(s)

    # Header
    names = [i["name"] for i in items]
    max_stat_w = max(len(s) for s in all_stats)
    col_w = max(max(len(n) for n in names), 8)

    header = f"{'Stat':<{max_stat_w}}  "
    header += "  ".join(f"{n:>{col_w}}" for n in names)
    if len(items) == 2:
        header += f"  {'Diff':>{col_w}}"
    print(header)
    print("-" * len(header))

    # Subtitle row
    sub = f"{'(ilvl / type)':<{max_stat_w}}  "
    for item in items:
        label = f"{item['item_level']} {item.get('type', '')}"
        sub += f"{label:>{col_w}}  "
    print(sub)
    print("-" * len(header))

    for stat in all_stats:
        vals: list[int] = []
        for item in items:
            if stat == "Armor":
                vals.append(item.get("armor", 0))
            else:
                vals.append(item["stats"].get(stat, 0))

        row = f"{stat:<{max_stat_w}}  "
        for v in vals:
            cell = f"+{v}" if v > 0 else ("-" if v == 0 else str(v))
            row += f"{cell:>{col_w}}  "

        if len(items) == 2:
            diff = vals[0] - vals[1]
            if diff > 0:
                cell = f"+{diff}"
            elif diff < 0:
                cell = str(diff)
            else:
                cell = "-"
            row += f"{cell:>{col_w}}"

        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Look up TBC item stats from cmangos DB"
    )
    parser.add_argument("item_ids", nargs="+", type=int, help="Item ID(s) to look up")
    parser.add_argument(
        "--compare", action="store_true", help="Side-by-side comparison with diff"
    )
    args = parser.parse_args()

    conn = _get_conn()
    items: list[dict] = []
    for item_id in args.item_ids:
        item = lookup_item(conn, item_id)
        if item is None:
            print(f"Item {item_id} not found in database.", file=sys.stderr)
            continue
        items.append(item)

    if not items:
        sys.exit(1)

    if args.compare and len(items) >= 2:
        print_compare(items)
    else:
        for item in items:
            print_item(item)


if __name__ == "__main__":
    main()
