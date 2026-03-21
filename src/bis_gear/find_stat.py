"""Find gear upgrades for a specific stat target (e.g. defense cap).

Usage:
    uv run find-stat data/prot-paladin.txt --stat defense --target 490
    uv run find-stat data/prot-paladin.txt --stat defense --target 490 --source dungeon
    uv run find-stat data/prot-paladin.txt --stat defense --target 490 --source boe
    uv run find-stat data/prot-paladin.txt --stat defense --target 490 --source rep
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from functools import cache
from pathlib import Path

from bis_gear.item_lookup import ARMOR_SUBCLASS, DB_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Maps our --stat argument to the stat_type ID in item_template
STAT_ALIASES: dict[str, int] = {
    "defense": 12,
    "dodge": 13,
    "parry": 14,
    "block": 15,
    "hit": 31,
    "crit": 32,
    "haste": 36,
    "expertise": 37,
    "resilience": 35,
}

# Maps cmangos stat_type IDs to wowsims stat names (for gem/enchant lookup)
STAT_TO_WOWSIMS: dict[int, str] = {
    12: "Defense",
    13: "Dodge",
    14: "Parry",
    15: "BlockValue",
    31: "MeleeHit",
    32: "MeleeCrit",
    35: "Resilience",
    36: "SpellHaste",
    37: "Expertise",
}

# Defense rating to defense skill conversion at level 70
DEFENSE_RATING_PER_SKILL = 2.3653
BASE_DEFENSE_SKILL = 350

# Crit cap constants (defense + resilience)
DEFENSE_SKILL_FOR_CAP = 140
RESILIENCE_RATING_FOR_CAP = 221

# Equippable slot IDs
EQUIP_SLOTS: dict[int, str] = {
    1: "Head",
    2: "Neck",
    3: "Shoulder",
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
    16: "Back",
    21: "Main Hand",
    23: "Held In Off-Hand",
    28: "Relic",
}

# Map candidate slot names to character JSON slot names
SLOT_ALIASES: dict[str, list[str]] = {
    "Shield": ["Off Hand"],
    "Held In Off-Hand": ["Off Hand"],
    "One-Hand": ["Main Hand"],
    "Finger": ["Finger 1", "Finger 2"],
    "Trinket": ["Trinket 1", "Trinket 2"],
}

REP_RANK_NAMES: dict[int, str] = {
    0: "None",
    1: "Hated",
    2: "Hostile",
    3: "Unfriendly",
    4: "Friendly",
    5: "Honored",
    6: "Revered",
    7: "Exalted",
}

QUALITY_NAMES: dict[int, str] = {
    0: "Poor",
    1: "Common",
    2: "Uncommon",
    3: "Rare",
    4: "Epic",
    5: "Legendary",
}

SLOT_ORDER = [
    "Head",
    "Neck",
    "Shoulder",
    "Back",
    "Chest",
    "Wrist",
    "Hands",
    "Waist",
    "Legs",
    "Feet",
    "Finger",
    "Trinket",
    "Main Hand",
    "One-Hand",
    "Shield",
    "Held In Off-Hand",
    "Relic",
]


@cache
def _load_gems_db() -> dict[int, dict]:
    """Load wowsims gems.json keyed by gem item ID."""
    path = PROJECT_ROOT / "sources" / "wowsims-tbc" / "gems.json"
    if not path.exists():
        return {}
    return {g["id"]: g for g in json.loads(path.read_text(encoding="utf-8"))}


@cache
def _load_enchants_db() -> dict[int, dict]:
    """Load wowsims enchants.json keyed by effect_id."""
    path = PROJECT_ROOT / "sources" / "wowsims-tbc" / "enchants.json"
    if not path.exists():
        return {}
    return {e["effect_id"]: e for e in json.loads(path.read_text(encoding="utf-8"))}


# Talent bonuses that grant defense skill (not rating).
# Key: (class, talent_tree_index, talent_position), Value: skill_per_point
DEFENSE_SKILL_TALENTS: dict[tuple[str, int, int], int] = {
    ("paladin", 1, 8): 4,  # Anticipation: +4 defense skill per point
}


def _get_talent_defense_skill(char_class: str, talents: str) -> int:
    """Parse talent string for defense skill bonuses."""
    if not talents:
        return 0
    trees = talents.split("-")
    total = 0
    for (cls, tree_idx, pos), skill_per_pt in DEFENSE_SKILL_TALENTS.items():
        if char_class.lower() != cls:
            continue
        if tree_idx < len(trees) and pos < len(trees[tree_idx]):
            points = int(trees[tree_idx][pos])
            total += points * skill_per_pt
    return total


def _get_wse_bonus_stat(raw_data: dict, wowsims_stat: str) -> float:
    """Sum gem + enchant contributions for a stat from WSE raw data."""
    gems_db = _load_gems_db()
    enchants_db = _load_enchants_db()
    total = 0.0
    for item in raw_data.get("gear", {}).get("items", []):
        if item is None:
            continue
        for gem_id in item.get("gems", []):
            if gem_id and gem_id in gems_db:
                total += gems_db[gem_id].get("stats", {}).get(wowsims_stat, 0)
        enchant_id = item.get("enchant")
        if enchant_id and enchant_id in enchants_db:
            total += enchants_db[enchant_id].get("stats", {}).get(wowsims_stat, 0)
    return total


def _get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"Error: TBC database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


def _get_stat_value(conn: sqlite3.Connection, item_id: int, stat_type_id: int) -> int:
    """Get the value of a specific stat_type from an item's stat columns."""
    cur = conn.cursor()
    cols = ",".join(f"stat_type{i},stat_value{i}" for i in range(1, 11))
    cur.execute(f"SELECT {cols} FROM item_template WHERE entry=?", (item_id,))
    row = cur.fetchone()
    if not row:
        return 0
    return sum(row[i * 2 + 1] for i in range(10) if row[i * 2] == stat_type_id)


@cache
def _get_faction_name(conn: sqlite3.Connection, faction_id: int) -> str:
    """Look up faction name from faction_store."""
    cur = conn.cursor()
    cur.execute("SELECT FactionName1 FROM faction_store WHERE Entry=?", (faction_id,))
    row = cur.fetchone()
    return row[0] if row else f"Faction {faction_id}"


def _get_instance_type(conn: sqlite3.Connection, creature_id: int) -> str:
    """Determine if a creature spawns in a 5-man dungeon, raid, or open world."""
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT map FROM creature WHERE id=?", (creature_id,))
    maps = cur.fetchall()
    for (map_id,) in maps:
        cur.execute("SELECT maxPlayers FROM instance_template WHERE map=?", (map_id,))
        row = cur.fetchone()
        if row:
            if row[0] <= 5:
                return "dungeon"
            if row[0] <= 10:
                return "raid10"
            return "raid"
    return "world"


def _is_heroic_creature(conn: sqlite3.Connection, creature_id: int) -> bool:
    """Check if a creature entry is a heroic version (referenced by another's HeroicEntry)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM creature_template WHERE HeroicEntry=?", (creature_id,)
    )
    return cur.fetchone()[0] > 0


def _get_item_source(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    """Determine how an item is obtained: dungeon drop, vendor, BoE, etc."""
    cur = conn.cursor()
    sources: list[dict] = []

    def _add_drop_source(
        creature_id: int,
        creature_name: str,
        creature_rank: int,
        drop_chance: float,
        comment: str,
    ) -> None:
        inst_type = _get_instance_type(conn, creature_id)
        is_heroic = _is_heroic_creature(conn, creature_id)
        sources.append(
            {
                "type": "drop",
                "creature_id": creature_id,
                "creature_name": creature_name,
                "creature_rank": creature_rank,
                "drop_chance": drop_chance,
                "comment": comment,
                "instance_type": inst_type,
                "is_heroic": is_heroic,
            }
        )

    # Check direct creature loot tables
    cur.execute(
        """SELECT clt.entry, clt.ChanceOrQuestChance, clt.comments,
                  ct.Name, ct.rank as creature_rank
           FROM creature_loot_template clt
           JOIN creature_template ct ON ct.entry = clt.entry
           WHERE clt.item = ?
           ORDER BY clt.ChanceOrQuestChance DESC""",
        (item_id,),
    )
    for row in cur.fetchall():
        if row[1] <= 0:
            continue
        _add_drop_source(row[0], row[3], row[4], row[1], row[2] or "")

    # Check reference_loot_template (items referenced via loot groups)
    cur.execute(
        "SELECT entry, comments FROM reference_loot_template WHERE item = ?",
        (item_id,),
    )
    for ref_row in cur.fetchall():
        ref_id = ref_row[0]
        ref_comment = ref_row[1] or ""
        cur2 = conn.cursor()
        cur2.execute(
            """SELECT clt.entry, clt.ChanceOrQuestChance, clt.comments,
                      ct.Name, ct.rank as creature_rank
               FROM creature_loot_template clt
               JOIN creature_template ct ON ct.entry = clt.entry
               WHERE clt.mincountOrRef = ?
               ORDER BY clt.ChanceOrQuestChance DESC""",
            (-ref_id,),
        )
        for row in cur2.fetchall():
            _add_drop_source(
                row[0], row[3], row[4], row[1], ref_comment or row[2] or ""
            )

    # Check vendor tables
    cur.execute(
        """SELECT nv.entry, nv.comments, ct.Name
           FROM npc_vendor nv
           JOIN creature_template ct ON ct.entry = nv.entry
           WHERE nv.item = ?""",
        (item_id,),
    )
    for row in cur.fetchall():
        sources.append(
            {"type": "vendor", "vendor_name": row[2], "comment": row[1] or ""}
        )

    # Also check npc_vendor_template
    cur.execute(
        """SELECT nvt.entry, nvt.comments
           FROM npc_vendor_template nvt
           WHERE nvt.item = ?""",
        (item_id,),
    )
    for row in cur.fetchall():
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT Name FROM creature_template WHERE VendorTemplateId=?", (row[0],)
        )
        for ct_row in cur2.fetchall():
            sources.append(
                {"type": "vendor", "vendor_name": ct_row[0], "comment": row[1] or ""}
            )

    return sources


def _classify_source(item: dict, sources: list[dict]) -> str:
    """Classify an item's acquisition method."""
    bonding = item.get("_bonding", 0)

    if bonding == 2:
        return "boe"

    if item.get("_rep_faction", 0) > 0:
        return "rep"

    # Check drop sources — prioritize dungeon over raid
    has_dungeon = False
    has_raid = False
    for src in sources:
        if src["type"] == "drop":
            inst = src.get("instance_type", "world")
            if inst == "dungeon":
                has_dungeon = True
            elif inst in ("raid", "raid10"):
                has_raid = True

    if has_dungeon:
        return "dungeon"
    if has_raid:
        return "raid"

    for src in sources:
        if src["type"] == "drop":
            return "drop"

    if sources:
        return "vendor"

    return "other"


WSE_SLOT_ORDER = [
    "Head",
    "Neck",
    "Shoulder",
    "Back",
    "Chest",
    "Wrist",
    "Hands",
    "Waist",
    "Legs",
    "Feet",
    "Finger 1",
    "Finger 2",
    "Trinket 1",
    "Trinket 2",
    "Main Hand",
    "Off Hand",
    "Ranged",
]


def _load_character(path: Path) -> dict:
    with open(path) as f:
        data = json.load(f)

    # Detect WSE format
    if "gear" in data and "items" in data.get("gear", {}):
        items = data["gear"]["items"]
        equipped: list[dict] = []
        for i, item in enumerate(items):
            if item is None or i >= len(WSE_SLOT_ORDER):
                continue
            item_id = item.get("id", 0)
            if not item_id:
                continue
            equipped.append(
                {
                    "slot": i + 1,
                    "slotName": WSE_SLOT_ORDER[i],
                    "itemId": item_id,
                    "itemName": f"ID:{item_id}",
                }
            )
        return {
            "name": data.get("name", "Unknown"),
            "class": data.get("class", ""),
            "talents": data.get("talents", ""),
            "equippedItems": equipped,
            "_wse_raw": data,  # Preserve for gem/enchant parsing
        }

    return data.get("character", data)


def _format_source(conn: sqlite3.Connection, item_info: dict) -> str:
    """Format source info for display."""
    parts: list[str] = []
    cls = item_info["classification"]

    if cls == "boe":
        parts.append("BoE")
    elif cls == "rep":
        rank = REP_RANK_NAMES.get(item_info["rep_rank"], "?")
        faction = _get_faction_name(conn, item_info["rep_faction"])
        parts.append(f"Rep: {faction} ({rank})")

    # Show best drop sources (prefer dungeon, skip duplicates)
    seen_creatures: set[str] = set()
    for src in item_info["sources"]:
        if len(parts) >= 2:
            break
        if src["type"] == "drop":
            name = src["creature_name"]
            # Skip duplicate creature names (normal+heroic have same name)
            base_name = name.rstrip(" (1)")
            if base_name in seen_creatures:
                continue
            seen_creatures.add(base_name)

            inst = src.get("instance_type", "world")
            heroic = src.get("is_heroic", False)

            label = name
            if heroic:
                label += " (H)"
            if inst == "dungeon":
                label = f"Dungeon: {label}"
            elif inst in ("raid", "raid10"):
                label = f"Raid: {label}"
            parts.append(label)
        elif src["type"] == "vendor" and cls not in ("boe", "rep"):
            parts.append(f"Vendor: {src['vendor_name']}")

    return " | ".join(parts) if parts else "unknown"


def find_stat_upgrades(
    conn: sqlite3.Connection,
    char: dict,
    stat_type_id: int,
    stat_name: str,
    target: int,
    source_filter: str | None = None,
    max_rep_rank: int = 5,
) -> None:
    """Find items with the target stat, grouped by slot, compared to current gear."""
    cur = conn.cursor()
    equipped = char["equippedItems"]
    equipped_by_slot: dict[str, dict] = {}
    for eq in equipped:
        equipped_by_slot[eq["slotName"]] = eq

    # Paladin class bitmask (class 2 = bit 1)
    char_class = char.get("class", "")
    class_bitmasks: dict[str, int] = {
        "Paladin": 2,
        "Warrior": 1,
        "Druid": 1024,
        "Shaman": 64,
        "Hunter": 4,
        "Rogue": 8,
        "Priest": 16,
        "Mage": 128,
        "Warlock": 256,
    }
    class_bit = class_bitmasks.get(char_class, 0)

    # Get current stat values per slot (base items from cmangos)
    current_stats: dict[str, int] = {}
    total_current = 0
    for eq in equipped:
        val = _get_stat_value(conn, eq["itemId"], stat_type_id)
        slot_name = eq["slotName"]
        current_stats[slot_name] = val
        total_current += val

    # Add gem + enchant contributions from WSE data
    wse_raw = char.get("_wse_raw")
    wowsims_stat = STAT_TO_WOWSIMS.get(stat_type_id, "")
    gem_enchant_bonus = 0.0
    if wse_raw and wowsims_stat:
        gem_enchant_bonus = _get_wse_bonus_stat(wse_raw, wowsims_stat)
    total_with_gems = total_current + gem_enchant_bonus

    # Talent-based defense skill bonus
    talent_defense_skill = 0
    if stat_name == "defense":
        talent_defense_skill = _get_talent_defense_skill(
            char.get("class", ""), char.get("talents", "")
        )

    # Defense gap calculation with crit cap
    if stat_name == "defense" and target > 0:
        base_def = BASE_DEFENSE_SKILL + talent_defense_skill
        current_defense = base_def + total_with_gems / DEFENSE_RATING_PER_SKILL
        needed_rating = (target - base_def) * DEFENSE_RATING_PER_SKILL
        gap = needed_rating - total_with_gems

        print(
            f"Base defense skill: {base_def} (350 base + {talent_defense_skill} talents)"
        )
        print(
            f"Current: {total_with_gems:.0f} rating = {current_defense:.1f} defense skill"
        )
        if gem_enchant_bonus > 0:
            print(
                f"  (items: {total_current}, gems/enchants: +{gem_enchant_bonus:.0f})"
            )
        print(f"Target:  {needed_rating:.0f} rating = {target} defense skill")

        if gap > 0:
            print(f"Gap:     {gap:.0f} more defense rating needed")
            # Show resilience alternative
            def_fraction = (
                current_defense - BASE_DEFENSE_SKILL
            ) / DEFENSE_SKILL_FOR_CAP
            resil_needed = max(
                0, round((1.0 - def_fraction) * RESILIENCE_RATING_FOR_CAP)
            )
            # Get current resilience from WSE if available
            current_resil = 0.0
            if wse_raw:
                current_resil = _get_wse_bonus_stat(wse_raw, "Resilience")
                for eq in equipped:
                    current_resil += _get_stat_value(conn, eq["itemId"], 35)
            resil_gap = max(0, resil_needed - current_resil)
            print(
                f"  Or: {resil_needed} resilience rating at current defense"
                f" (have {current_resil:.0f}, need {resil_gap:.0f} more)"
            )
        else:
            print("CRIT CAPPED!")
    else:
        print(f"Current total {stat_name} rating from gear: {total_with_gems:.0f}")
        if gem_enchant_bonus > 0:
            print(
                f"  (items: {total_current}, gems/enchants: +{gem_enchant_bonus:.0f})"
            )
    print()

    # Find all candidate items with this stat
    conditions = " OR ".join(
        f"(stat_type{i}={stat_type_id} AND stat_value{i}>0)" for i in range(1, 11)
    )
    class_filter = (
        f"AND (AllowableClass = -1 OR (AllowableClass & {class_bit}) > 0)"
        if class_bit
        else ""
    )
    cur.execute(
        f"""SELECT entry, name, Quality, ItemLevel, RequiredLevel, InventoryType,
                   bonding, RequiredReputationFaction, RequiredReputationRank,
                   AllowableClass, class, subclass
            FROM item_template
            WHERE ({conditions})
            AND RequiredLevel <= 70
            AND ItemLevel >= 85
            AND Quality >= 2
            {class_filter}
            ORDER BY ItemLevel DESC"""
    )

    # Group candidates by slot
    candidates_by_slot: dict[str, list[dict]] = {}
    for row in cur.fetchall():
        item_id, name, quality, ilvl, req_level, inv_type = row[:6]
        bonding, rep_faction, rep_rank, allow_class = row[6:10]
        item_class, item_subclass = row[10:12]

        if inv_type not in EQUIP_SLOTS:
            continue

        slot_name = EQUIP_SLOTS[inv_type]

        stat_val = _get_stat_value(conn, item_id, stat_type_id)
        if stat_val <= 0:
            continue

        sources = _get_item_source(conn, item_id)

        # Determine armor type tag for non-optimal armor
        armor_tag = ""
        if item_class == 4 and item_subclass in (1, 2, 3):  # Cloth/Leather/Mail
            armor_tag = f" [{ARMOR_SUBCLASS.get(item_subclass, '')}]"

        item_info = {
            "id": item_id,
            "name": name,
            "quality": quality,
            "ilvl": ilvl,
            "slot": slot_name,
            "stat_value": stat_val,
            "bonding": bonding,
            "_bonding": bonding,
            "_rep_faction": rep_faction,
            "rep_faction": rep_faction,
            "rep_rank": rep_rank,
            "sources": sources,
            "armor_tag": armor_tag,
        }

        classification = _classify_source(item_info, sources)
        item_info["classification"] = classification

        # Apply filters
        if source_filter == "dungeon" and classification != "dungeon":
            continue
        if source_filter == "boe" and classification != "boe":
            continue
        if source_filter == "rep" and classification != "rep":
            continue
        if source_filter == "easy":
            if classification == "boe":
                if quality > 3:  # Only rare BoEs, not epic
                    continue
            elif classification == "rep":
                if rep_rank > max_rep_rank:
                    continue
            elif classification == "dungeon":
                pass  # All dungeon drops are fine
            else:
                continue  # Skip raid, world, vendor, other

        candidates_by_slot.setdefault(slot_name, []).append(item_info)

    # Print results grouped by slot
    for slot_name in SLOT_ORDER:
        candidates = candidates_by_slot.get(slot_name, [])
        if not candidates:
            continue

        current_val = 0
        current_item_name = "(empty)"
        match_slots = SLOT_ALIASES.get(slot_name, []) + [slot_name]
        for eq_slot, eq_data in equipped_by_slot.items():
            if eq_slot in match_slots or eq_slot.startswith(slot_name):
                v = _get_stat_value(conn, eq_data["itemId"], stat_type_id)
                if v >= current_val:
                    current_val = v
                    current_item_name = eq_data["itemName"]

        print(
            f"=== {slot_name} (current: {current_item_name}, "
            f"{stat_name}+{current_val}) ==="
        )

        candidates.sort(key=lambda c: c["stat_value"], reverse=True)

        seen: set[int] = set()
        shown = 0
        for c in candidates:
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            if shown >= 10:
                break
            shown += 1

            diff = c["stat_value"] - current_val
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            qual = QUALITY_NAMES.get(c["quality"], "?")
            source_str = _format_source(conn, c)
            tag = c.get("armor_tag", "")

            print(
                f"  {c['name'] + tag:45s} ilvl{c['ilvl']:3d} {qual:6s} "
                f"{stat_name}+{c['stat_value']:<3d} ({diff_str:>4s})  "
                f"{source_str}"
            )

        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find gear upgrades for a specific stat target"
    )
    parser.add_argument("character_file", type=Path, help="Path to character JSON")
    parser.add_argument(
        "--stat",
        required=True,
        choices=list(STAT_ALIASES.keys()),
        help="Stat to search for",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=0,
        help="Target stat value (e.g. 490 for defense cap)",
    )
    parser.add_argument(
        "--source",
        choices=["dungeon", "boe", "rep", "easy", "all"],
        default="easy",
        help="Filter by source: easy (default) = dungeons + honored rep + rare BoE",
    )
    args = parser.parse_args()

    conn = _get_conn()
    char = _load_character(args.character_file)
    stat_type_id = STAT_ALIASES[args.stat]

    source_filter = None if args.source == "all" else args.source

    print(f"Finding {args.stat} rating upgrades for {char['name']}")
    print()

    find_stat_upgrades(conn, char, stat_type_id, args.stat, args.target, source_filter)


if __name__ == "__main__":
    main()
