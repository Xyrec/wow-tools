"""
Parses AtlasLoot TBC BiS Lua files into structured JSON.

AtlasLoot stores BiS lists as Lua tables with item IDs ordered by priority
(position 1 = best, position 2 = next best, etc.). This parser extracts
the item lists per slot and maps them to our canonical format, enriching
each item with source info from the cmangos DB.

Usage:
    uv run al-parse --spec resto
    uv run al-parse --spec ele
    uv run al-parse --spec prot

Spec aliases: resto, resto-shaman | ele, elemental, elemental-shaman | prot, prot-paladin
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SOURCES_DIR = PROJECT_ROOT / "sources" / "atlasloot"
DB_PATH = PROJECT_ROOT / "sources" / "cmangos-tbc-db" / "tbcmangos.sqlite"

_SPEC_ALIASES: dict[str, str] = {
    "resto": "resto-shaman",
    "resto-shaman": "resto-shaman",
    "ele": "elemental-shaman",
    "elemental": "elemental-shaman",
    "elemental-shaman": "elemental-shaman",
    "prot": "prot-paladin",
    "protection": "prot-paladin",
    "prot-paladin": "prot-paladin",
}

# Map our spec slugs to AtlasLoot data keys per phase file.
# Keys vary across phases (e.g. "ShamanResto" in P0, "ShamanRestoration" in P1).
_SPEC_LUA_KEYS: dict[str, list[tuple[str, str]]] = {
    "resto-shaman": [
        ("prebisDB.lua", "ShamanResto"),
        ("phaseoneDB.lua", "ShamanRestoration"),
        ("phasetwoDB.lua", "ShamanRestoration_P2"),
    ],
    "elemental-shaman": [
        ("prebisDB.lua", "ShamanEle"),
        ("phaseoneDB.lua", "ShamanElemental"),
        ("phasetwoDB.lua", "ShamanElemental_P2"),
    ],
    "prot-paladin": [
        ("prebisDB.lua", "PalProt"),
        ("phaseoneDB.lua", "PaladinProtection_P1"),
        ("phasetwoDB.lua", "PaladinProtection_P2"),
    ],
}

# Map phase DB filenames to phase keys
_PHASE_MAP: dict[str, str] = {
    "prebisDB.lua": "phase-0",
    "phaseoneDB.lua": "phase-1",
    "phasetwoDB.lua": "phase-2",
}

# Map AtlasLoot slot names to our canonical slot keys
_SLOT_MAP: dict[str, str] = {
    "Head": "head",
    "Shoulders": "shoulders",
    "Back": "back",
    "Chest": "chest",
    "Wrist": "wrists",
    "Hands": "hands",
    "Waist": "waist",
    "Legs": "legs",
    "Feet": "feet",
    "Neck": "neck",
    "Rings": "rings",
    "Trinkets": "trinkets",
    "Main Hand": "weapons",
    "Onehand": "weapons",
    "Off Hand": "offhands",
    "Offhand": "offhands",
    "Shield": "offhands",
    "Twohand": "weapons",
    "Ranged": "totems",
    "Wand": "totems",
    "Totems": "totems",
}

# TBC instance map IDs to names
_INSTANCE_NAMES: dict[int, str] = {
    269: "Black Morass",
    532: "Karazhan",
    534: "Hyjal Summit",
    540: "Shattered Halls",
    542: "Blood Furnace",
    543: "Hellfire Ramparts",
    544: "Magtheridon's Lair",
    545: "Steamvault",
    546: "Underbog",
    547: "Slave Pens",
    548: "Serpentshrine Cavern",
    550: "Tempest Keep",
    552: "Arcatraz",
    553: "Botanica",
    554: "Mechanar",
    555: "Shadow Labyrinth",
    556: "Sethekk Halls",
    557: "Mana-Tombs",
    558: "Auchenai Crypts",
    560: "Old Hillsbrad Foothills",
    564: "Black Temple",
    565: "Gruul's Lair",
    568: "Zul'Aman",
    580: "Sunwell Plateau",
    585: "Magisters' Terrace",
}

# Reputation rank IDs to names
_REP_RANKS: dict[int, str] = {
    4: "Friendly",
    5: "Honored",
    6: "Revered",
    7: "Exalted",
}

# Known badge vendor NPC entries (G'eras, Smith Hauthaa, etc.)
_BADGE_VENDORS: set[int] = {18525, 25046, 27666}

# Known PvP vendor NPC entries
_PVP_VENDOR_NAMES = {"arena", "gladiator", "pvp", "honor", "conquest", "battleground"}

# Tier token vendors → {InventoryType: (boss_name, instance_name)}.
# Maps the vendor who redeems tier tokens to the raid boss that drops each slot's token.
_TIER_TOKEN_SOURCES: dict[str, dict[int, tuple[str, str]]] = {
    "arodis sunblade": {  # T4
        1: ("Prince Malchezaar", "Karazhan"),  # Head
        3: ("High King Maulgar", "Gruul's Lair"),  # Shoulders
        5: ("Magtheridon", "Magtheridon's Lair"),  # Chest
        7: ("Gruul the Dragonkiller", "Gruul's Lair"),  # Legs
        10: ("The Curator", "Karazhan"),  # Hands
        20: ("Magtheridon", "Magtheridon's Lair"),  # Chest (Robe)
    },
    "veynna dawnstar": {  # T5
        1: ("Lady Vashj", "Serpentshrine Cavern"),  # Head
        3: ("Void Reaver", "Tempest Keep"),  # Shoulders
        5: ("Kael'thas Sunstrider", "Tempest Keep"),  # Chest
        7: ("Fathom-Lord Karathress", "Serpentshrine Cavern"),  # Legs
        10: ("Leotheras the Blind", "Serpentshrine Cavern"),  # Hands
        20: ("Kael'thas Sunstrider", "Tempest Keep"),  # Chest (Robe)
    },
}


def _build_dungeon_item_lookup() -> dict[int, str]:
    """Parse AtlasLoot DungeonsAndRaids data-tbc.lua into {item_id: source_string}.

    Source strings match the format used by IV/WTBC parsers, e.g.:
      "Drop: Prince Malchezaar — Karazhan"
      "Drop: Watchkeeper Gargolmar (Hellfire Ramparts)"
    """
    lua_path = SOURCES_DIR / "AtlasLootClassic_DungeonsAndRaids" / "data-tbc.lua"
    if not lua_path.exists():
        return {}

    text = lua_path.read_text(encoding="utf-8")
    result: dict[int, str] = {}

    # Resolve AL["..."] strings used for instance/boss names.
    # We don't have the locale table, but boss names are mostly in AL["Name"]
    # format. We'll extract them as-is since they're English in the source.

    # Parse each instance block: data["Key"] = { ... InstanceID = N ... items = { ... } }
    instance_pattern = r'data\["([^"]+)"\]\s*=\s*\{(.*?)(?=\ndata\["|$)'

    for inst_match in re.finditer(instance_pattern, text, re.DOTALL):
        inst_key = inst_match.group(1)
        inst_block = inst_match.group(2)

        # Get InstanceID (map ID) — dungeons/raids have this
        iid_match = re.search(r"InstanceID\s*=\s*(\d+)", inst_block)
        map_id = int(iid_match.group(1)) if iid_match else None
        inst_name = _INSTANCE_NAMES.get(map_id, inst_key) if map_id else inst_key

        # Determine if dungeon or raid from ContentType
        is_raid = (
            "RAID" in inst_block.split("items")[0] if "items" in inst_block else False
        )
        is_world_boss = "WorldBoss" in inst_key

        # Determine max players for source string formatting
        if is_world_boss:
            max_players = 0  # world boss
        elif is_raid:
            max_players = 25  # raids use " — " separator
        else:
            max_players = 5  # dungeons use " ()" format

        # Parse boss blocks within items = { ... }
        # Each boss: { name = AL["Boss Name"] or name = "string", ... [NORMAL_DIFF] = { items }, [HEROIC_DIFF] = { items } }
        # Boss blocks are separated by }, {
        boss_pattern = r'name\s*=\s*(?:AL\["([^"]+)"\]|format\([^,]+,\s*AL\["([^"]+)"\]\)|"([^"]+)")'
        # Split on boss entries — find each name followed by item lists
        # We need to pair each boss name with its items
        boss_splits = list(re.finditer(boss_pattern, inst_block))

        for i, boss_match in enumerate(boss_splits):
            boss_name = (
                boss_match.group(1) or boss_match.group(2) or boss_match.group(3)
            )
            if not boss_name:
                continue

            # Get the text from this boss to the next boss (or end)
            start = boss_match.end()
            end = (
                boss_splits[i + 1].start()
                if i + 1 < len(boss_splits)
                else len(inst_block)
            )
            boss_block = inst_block[start:end]

            # Extract item IDs separately for normal and heroic
            normal_ids: set[int] = set()
            heroic_ids: set[int] = set()

            # Split boss_block into NORMAL_DIFF and HEROIC_DIFF sections.
            # Use lookahead to capture everything up to the next [*_DIFF] or
            # end of boss block, avoiding the nested-brace truncation issue.
            normal_match = re.search(
                r"\[NORMAL_DIFF\]\s*=\s*\{(.*?)(?=\[HEROIC_DIFF\]|\[NORMAL_DIFF\]|\Z)",
                boss_block,
                re.DOTALL,
            )
            heroic_match = re.search(
                r"\[HEROIC_DIFF\]\s*=\s*\{(.*?)(?=\[NORMAL_DIFF\]|\[HEROIC_DIFF\]|\Z)",
                boss_block,
                re.DOTALL,
            )
            if normal_match:
                normal_ids = {
                    int(m)
                    for m in re.findall(
                        r"\{\s*\d+\s*,\s*(\d+)\s*\}", normal_match.group(1)
                    )
                }
            if heroic_match:
                heroic_ids = {
                    int(m)
                    for m in re.findall(
                        r"\{\s*\d+\s*,\s*(\d+)\s*\}", heroic_match.group(1)
                    )
                }
            # Items only in heroic (not in normal) are heroic-only
            heroic_only = heroic_ids - normal_ids
            all_ids = normal_ids | heroic_ids

            # Build source strings
            for item_id in all_ids:
                if item_id in result:
                    continue
                heroic_tag = " (H)" if item_id in heroic_only else ""
                if is_world_boss:
                    source = f"World Boss: {boss_name}"
                elif max_players <= 5:
                    source = f"Drop: {boss_name}{heroic_tag} ({inst_name})"
                else:
                    source = f"Drop: {boss_name} — {inst_name}"
                result[item_id] = source

    return result


def _load_item_info(
    conn: sqlite3.Connection, item_ids: set[int]
) -> dict[int, tuple[str, int]]:
    """Bulk-load item names and InventoryType from the cmangos DB.

    Returns {item_id: (name, inventory_type)}.
    """
    if not item_ids:
        return {}
    placeholders = ",".join("?" for _ in item_ids)
    cur = conn.cursor()
    cur.execute(
        f"SELECT entry, name, InventoryType FROM item_template WHERE entry IN ({placeholders})",  # noqa: S608
        list(item_ids),
    )
    return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


def _classify_item_sources(
    conn: sqlite3.Connection, item_ids: set[int]
) -> dict[int, str]:
    """Determine the source string for each item from the cmangos DB.

    Checks (in priority order):
    1. Creature drops (dungeon/raid) via loot tables, with heroic creature resolution
    2. Reputation vendor items (RequiredReputationFaction on item_template)
    3. Badge/PvP vendors via npc_vendor
    4. Tier set / PvP vendors via npc_vendor_template
    5. Quest rewards
    6. Crafted items (created by a spell in spell_template)
    7. BoE world drops (bonding = 2, no other source found)
    """
    if not item_ids or not conn:
        return {}

    cur = conn.cursor()
    sources: dict[int, str] = {}
    remaining = set(item_ids)

    # --- Step 0a: BoE items are world drops regardless of loot tables ---
    placeholders = ",".join("?" for _ in remaining)
    cur.execute(
        f"SELECT entry FROM item_template WHERE entry IN ({placeholders}) AND bonding = 2",  # noqa: S608
        list(remaining),
    )
    for (item_id,) in cur.fetchall():
        sources[item_id] = "Auction House — BoE World Drop"
        remaining.discard(item_id)

    # --- Step 0b: AtlasLoot dungeon/raid data (most reliable source) ---
    al_dungeon_lookup = _build_dungeon_item_lookup()
    for item_id in list(remaining):
        if item_id in al_dungeon_lookup:
            sources[item_id] = al_dungeon_lookup[item_id]
            remaining.discard(item_id)

    # --- Build encounter name -> map lookup for scripted bosses ---
    cur.execute("SELECT MapId, EncounterName FROM instance_dungeon_encounters")
    encounter_maps: dict[str, int] = {}
    for map_id, enc_name in cur.fetchall():
        encounter_maps[enc_name.lower().strip()] = map_id

    # --- Helper: resolve creature to instance ---
    def _get_creature_instance(creature_id: int) -> tuple[str, str, int] | None:
        """Returns (creature_name, instance_name, max_players) or None."""
        cur.execute("SELECT name FROM creature_template WHERE entry=?", (creature_id,))
        name_row = cur.fetchone()
        if not name_row:
            return None
        creature_name = name_row[0].removesuffix(" (1)")

        # Try direct spawn location first
        cur.execute("SELECT map FROM creature WHERE id=? LIMIT 1", (creature_id,))
        map_row = cur.fetchone()

        # If no spawn, try the base creature (heroic variant resolution)
        if not map_row:
            cur.execute(
                "SELECT entry FROM creature_template WHERE HeroicEntry=?",
                (creature_id,),
            )
            base_row = cur.fetchone()
            if base_row:
                cur.execute(
                    "SELECT map FROM creature WHERE id=? LIMIT 1", (base_row[0],)
                )
                map_row = cur.fetchone()

        # If still no spawn, match creature name against instance encounters
        if not map_row:
            enc_map_id = encounter_maps.get(creature_name.lower())
            if enc_map_id:
                map_row = (enc_map_id,)

        if not map_row:
            return None
        map_id = map_row[0]
        inst_name = _INSTANCE_NAMES.get(map_id)
        if not inst_name:
            return None
        cur.execute("SELECT maxPlayers FROM instance_template WHERE map=?", (map_id,))
        inst_row = cur.fetchone()
        if not inst_row:
            return None
        return (creature_name, inst_name, inst_row[0])

    # --- Step 1: Creature drops ---
    # Reference loot: item -> ref_entry -> creature
    placeholders = ",".join("?" for _ in remaining)
    cur.execute(
        f"SELECT item, entry FROM reference_loot_template WHERE item IN ({placeholders})",  # noqa: S608
        list(remaining),
    )
    ref_map: dict[int, list[int]] = {}
    for item_id, ref_entry in cur.fetchall():
        ref_map.setdefault(item_id, []).append(ref_entry)

    all_ref_entries = set()
    for refs in ref_map.values():
        all_ref_entries.update(refs)

    ref_to_creatures: dict[int, list[int]] = {}
    if all_ref_entries:
        neg_refs = [-r for r in all_ref_entries]
        placeholders2 = ",".join("?" for _ in neg_refs)
        cur.execute(
            f"SELECT mincountOrRef, entry FROM creature_loot_template WHERE mincountOrRef IN ({placeholders2})",  # noqa: S608
            neg_refs,
        )
        for neg_ref, creature_id in cur.fetchall():
            ref_to_creatures.setdefault(-neg_ref, []).append(creature_id)

    # Direct creature loot
    placeholders = ",".join("?" for _ in remaining)
    cur.execute(
        f"SELECT item, entry FROM creature_loot_template WHERE item IN ({placeholders})",  # noqa: S608
        list(remaining),
    )
    direct_drops: dict[int, list[int]] = {}
    for item_id, creature_id in cur.fetchall():
        direct_drops.setdefault(item_id, []).append(creature_id)

    for item_id in list(remaining):
        creatures: set[int] = set()
        for ref_entry in ref_map.get(item_id, []):
            creatures.update(ref_to_creatures.get(ref_entry, []))
        creatures.update(direct_drops.get(item_id, []))

        best: tuple[str, str, int] | None = None
        for cid in creatures:
            info = _get_creature_instance(cid)
            if not info:
                continue
            if best is None or info[2] > best[2]:
                best = info

        if best:
            creature_name, inst_name, max_players = best
            if max_players <= 5:
                sources[item_id] = f"Drop: {creature_name} ({inst_name})"
            else:
                sources[item_id] = f"Drop: {creature_name} — {inst_name}"
            remaining.discard(item_id)

    # --- Step 2: Reputation vendor items ---
    if remaining:
        placeholders = ",".join("?" for _ in remaining)
        cur.execute(
            f"SELECT entry, RequiredReputationFaction, RequiredReputationRank "
            f"FROM item_template WHERE entry IN ({placeholders}) "
            f"AND RequiredReputationFaction > 0",  # noqa: S608
            list(remaining),
        )
        for item_id, faction_id, rank_id in cur.fetchall():
            cur.execute(
                "SELECT FactionName1 FROM faction_store WHERE Entry=?",
                (faction_id,),
            )
            fname_row = cur.fetchone()
            faction_name = fname_row[0] if fname_row else f"Faction {faction_id}"
            rank_name = _REP_RANKS.get(rank_id, f"Rank {rank_id}")
            sources[item_id] = f"{faction_name} — {rank_name}"
            remaining.discard(item_id)

    # --- Step 3: Badge and PvP vendors (npc_vendor) ---
    if remaining:
        placeholders = ",".join("?" for _ in remaining)
        cur.execute(
            f"SELECT item, entry, ExtendedCost FROM npc_vendor WHERE item IN ({placeholders})",  # noqa: S608
            list(remaining),
        )
        vendor_rows: dict[int, list[tuple[int, int]]] = {}
        for item_id, vendor_id, ext_cost in cur.fetchall():
            vendor_rows.setdefault(item_id, []).append((vendor_id, ext_cost))

        for item_id, vendors in vendor_rows.items():
            if item_id not in remaining:
                continue
            for vendor_id, ext_cost in vendors:
                if vendor_id in _BADGE_VENDORS:
                    sources[item_id] = "Badge of Justice Vendor"
                    remaining.discard(item_id)
                    break
            if item_id not in remaining:
                continue
            for vendor_id, ext_cost in vendors:
                cur.execute(
                    "SELECT name FROM creature_template WHERE entry=?",
                    (vendor_id,),
                )
                vrow = cur.fetchone()
                if vrow:
                    vname_lower = vrow[0].lower()
                    if any(kw in vname_lower for kw in _PVP_VENDOR_NAMES):
                        sources[item_id] = "PvP Vendor"
                        remaining.discard(item_id)
                        break

    # --- Step 4: Tier set / PvP vendors (npc_vendor_template) ---
    if remaining:
        placeholders = ",".join("?" for _ in remaining)
        cur.execute(
            f"SELECT item, entry, ExtendedCost FROM npc_vendor_template "
            f"WHERE item IN ({placeholders})",  # noqa: S608
            list(remaining),
        )
        template_rows: dict[int, list[tuple[int, int]]] = {}
        for item_id, template_id, ext_cost in cur.fetchall():
            template_rows.setdefault(item_id, []).append((template_id, ext_cost))

        for item_id, templates in template_rows.items():
            if item_id not in remaining:
                continue
            for template_id, ext_cost in templates:
                # Find creature(s) using this vendor template
                cur.execute(
                    "SELECT name FROM creature_template WHERE VendorTemplateId=? LIMIT 1",
                    (template_id,),
                )
                ct_row = cur.fetchone()
                if not ct_row:
                    continue
                vendor_name = ct_row[0].lower()
                if any(kw in vendor_name for kw in _PVP_VENDOR_NAMES):
                    sources[item_id] = "PvP Vendor"
                elif vendor_name in _TIER_TOKEN_SOURCES:
                    # Tier token vendor — resolve to the raid boss that drops the token
                    cur.execute(
                        "SELECT InventoryType FROM item_template WHERE entry=?",
                        (item_id,),
                    )
                    inv_row = cur.fetchone()
                    slot_map = _TIER_TOKEN_SOURCES[vendor_name]
                    token_info = slot_map.get(inv_row[0]) if inv_row else None
                    if token_info:
                        boss_name, inst_name = token_info
                        sources[item_id] = (
                            f"Drop: {boss_name} — {inst_name} (Tier Token)"
                        )
                    else:
                        sources[item_id] = f"Vendor: {ct_row[0]}"
                else:
                    sources[item_id] = f"Vendor: {ct_row[0]}"
                remaining.discard(item_id)
                break

    # --- Step 5: Quest rewards ---
    if remaining:
        placeholders = ",".join("?" for _ in remaining)
        cur.execute(
            f"SELECT Title, RewChoiceItemId1, RewChoiceItemId2, RewChoiceItemId3, "
            f"RewChoiceItemId4, RewItemId1, RewItemId2, RewItemId3, RewItemId4 "
            f"FROM quest_template WHERE "
            f"RewChoiceItemId1 IN ({placeholders}) OR RewChoiceItemId2 IN ({placeholders}) OR "
            f"RewChoiceItemId3 IN ({placeholders}) OR RewChoiceItemId4 IN ({placeholders}) OR "
            f"RewItemId1 IN ({placeholders}) OR RewItemId2 IN ({placeholders}) OR "
            f"RewItemId3 IN ({placeholders}) OR RewItemId4 IN ({placeholders})",  # noqa: S608
            list(remaining) * 8,
        )
        for row in cur.fetchall():
            title = row[0]
            reward_ids = set(row[1:]) - {0}
            for item_id in reward_ids & remaining:
                sources[item_id] = f"Quest: {title}"
                remaining.discard(item_id)

    # --- Step 6: Crafted items ---
    if remaining:
        placeholders = ",".join("?" for _ in remaining)
        cur.execute(
            f"SELECT EffectItemType1 FROM spell_template WHERE EffectItemType1 IN ({placeholders})",  # noqa: S608
            list(remaining),
        )
        crafted = {row[0] for row in cur.fetchall()}
        for item_id in crafted:
            sources[item_id] = "Profession: Crafted"
            remaining.discard(item_id)

    # --- Step 7: BoE world drops ---
    if remaining:
        placeholders = ",".join("?" for _ in remaining)
        cur.execute(
            f"SELECT entry, bonding FROM item_template WHERE entry IN ({placeholders})",  # noqa: S608
            list(remaining),
        )
        for item_id, bonding in cur.fetchall():
            if bonding == 2:  # BoE
                sources[item_id] = "Auction House — BoE World Drop"
                remaining.discard(item_id)

    # Anything left is non-TBC content (classic raids, seasonal events, etc.)
    for item_id in remaining:
        sources[item_id] = "Other (Classic, Seasonal Event, Etc.)"

    return sources


def parse_spec_from_lua(lua_text: str, spec_key: str) -> dict[str, list[int]]:
    """Extract slot → [item_ids] for a given spec key from Lua source.

    The Lua format is:
        data["SpecKey"] = { name = ..., items = {
            { name = format(AL["Head"], "1"), [NORMAL_DIFF] = { { 1, 29028 }, ... } },
            { name = format(AL["Shoulders"], "2"), ... },
            ...
        } }
    """
    # Find the data block for this spec
    pattern = rf'data\["{re.escape(spec_key)}"\]\s*=\s*\{{(.*?)(?=data\["|$)'
    match = re.search(pattern, lua_text, re.DOTALL)
    if not match:
        return {}

    block = match.group(1)

    # Find each slot block: format(AL["SlotName"], ...) followed by items.
    # Items are nested: [NORMAL_DIFF] = { { 1, id }, { 2, id }, ... },  }
    # We match to }, } to get the full outer closing brace.
    slot_pattern = (
        r'format\(AL\["([^"]+)"\][^}]*\[NORMAL_DIFF\]\s*=\s*\{(.*?)\}\s*,\s*\}'
    )
    slots: dict[str, list[int]] = {}

    for slot_match in re.finditer(slot_pattern, block, re.DOTALL):
        al_name = slot_match.group(1)
        items_text = slot_match.group(2)

        canonical = _SLOT_MAP.get(al_name)
        if canonical is None:
            continue

        # Extract item IDs: { position, item_id }
        item_ids = [
            int(m) for m in re.findall(r"\{\s*\d+\s*,\s*(\d+)\s*\}", items_text)
        ]

        if canonical in slots:
            # Some specs have both "Main Hand" and "Twohand" mapping to "weapons"
            slots[canonical].extend(item_ids)
        else:
            slots[canonical] = item_ids

    return slots


def resolve_spec(raw: str) -> str:
    key = raw.strip().lower()
    if key not in _SPEC_ALIASES:
        print(f"Unknown spec '{raw}'. Use: resto, ele, prot.")
        sys.exit(1)
    return _SPEC_ALIASES[key]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse AtlasLoot TBC BiS Lua files into JSON"
    )
    parser.add_argument(
        "--spec", required=True, help="Spec to parse (resto, ele, prot)"
    )
    parser.add_argument(
        "--output", help="Output JSON path (default: output/<spec>/al_bis_gear.json)"
    )
    args = parser.parse_args()

    spec = resolve_spec(args.spec)
    lua_keys = _SPEC_LUA_KEYS.get(spec)
    if not lua_keys:
        print(f"No AtlasLoot key mapping for spec '{spec}'.")
        sys.exit(1)

    # Read current phase
    current_phase_file = PROJECT_ROOT / "data" / "current-phase.txt"
    current_phase = (
        current_phase_file.read_text(encoding="utf-8").strip()
        if current_phase_file.exists()
        else None
    )

    # Connect to cmangos DB
    conn = sqlite3.connect(str(DB_PATH)) if DB_PATH.exists() else None

    # Collect all item IDs first for bulk lookups
    all_phase_data: list[tuple[str, dict[str, list[int]]]] = []
    all_item_ids: set[int] = set()

    for lua_filename, spec_lua_key in lua_keys:
        phase_key = _PHASE_MAP[lua_filename]

        # Find the lua file in the atlasloot source dirs
        lua_path = None
        for subdir in SOURCES_DIR.iterdir():
            candidate = subdir / lua_filename
            if candidate.exists():
                lua_path = candidate
                break

        if lua_path is None:
            print(f"Warning: {lua_filename} not found, skipping {phase_key}")
            continue

        lua_text = lua_path.read_text(encoding="utf-8")
        slots = parse_spec_from_lua(lua_text, spec_lua_key)

        if not slots:
            print(f"Warning: spec key '{spec_lua_key}' not found in {lua_filename}")
            continue

        for ids in slots.values():
            all_item_ids.update(ids)
        all_phase_data.append((phase_key, slots))

    # Bulk load item info and sources
    item_info: dict[int, tuple[str, int]] = {}
    item_sources: dict[int, str] = {}
    if conn and all_item_ids:
        item_info = _load_item_info(conn, all_item_ids)
        item_sources = _classify_item_sources(conn, all_item_ids)

    # Build output in the same format as iv/wtbc parsers
    result: dict = {}
    if current_phase:
        result["current_phase"] = current_phase

    phases: dict[str, dict] = {}
    for phase_key, slots in all_phase_data:
        phase_slots: dict[str, list[dict]] = {}
        for slot_key, item_ids in slots.items():
            items: list[dict] = []
            seen: set[int] = set()
            rank_idx = 0
            for item_id in item_ids:
                if item_id in seen:
                    continue
                seen.add(item_id)
                # Skip non-equippable items (tokens, quest items)
                info = item_info.get(item_id)
                if info and info[1] == 0:  # InventoryType 0 = Non-equippable
                    continue
                # Top 3 = BiS, 4-9 = Option, rest dropped
                if rank_idx < 3:
                    rank = "BiS"
                elif rank_idx < 9:
                    rank = "Option"
                else:
                    break
                rank_idx += 1
                name = info[0] if info else f"Unknown ({item_id})"
                source = item_sources.get(item_id, "Unknown")
                items.append(
                    {
                        "rank": rank,
                        "item_id": item_id,
                        "source": source,
                        "name": name,
                    }
                )
            phase_slots[slot_key] = items
        phases[phase_key] = phase_slots
        slot_count = len(phase_slots)
        item_count = sum(len(v) for v in phase_slots.values())
        print(f"  {phase_key}: {slot_count} slots, {item_count} items")

    result["phases"] = phases

    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT / "output" / spec / "al_bis_gear.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
