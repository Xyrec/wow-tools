"""
Compare equipped gear against Phase 0 and current-phase BiS lists.

Priority: current phase is authoritative. Phase 0 is only consulted as a
fallback when an item or upgrade doesn't appear in the current phase at all.

Usage:
    bis-gear --spec resto              # loads data/resto.json by default
    bis-gear --spec ele                # loads data/elemental.json by default
    bis-gear --spec resto custom.json  # explicit character file
    bis-gear --spec ele -              # read from stdin

Spec aliases: resto, resto-shaman | ele, elemental, elemental-shaman

Reads current-phase.txt and output/{spec}/bis_gear.json from the project directory.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Project root is two levels up from src/bis_gear/
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Map character slot names to BiS JSON slot keys.
# resolve_slot_key() handles variant keys across specs/phases.
SLOT_MAP = {
    "Head": "head",
    "Neck": "neck",
    "Shoulder": "shoulders",
    "Back": "back",
    "Chest": "chest",
    "Wrist": "wrists",
    "Hands": "hands",
    "Waist": "waist",
    "Legs": "legs",
    "Feet": "feet",
    "Finger 1": "rings",
    "Finger 2": "rings",
    "Trinket 1": "trinkets",
    "Trinket 2": "trinkets",
    "Main Hand": "weapons",
    "Off Hand": "offhands",
    "Ranged": "totems",
}

FACTION_NAMES = [
    "Honor Hold",
    "Thrallmar",
    "Cenarion Expedition",
    "Lower City",
    "The Sha'tar",
    "The Aldor",
    "The Scryers",
    "Keepers of Time",
    "Kurenai",
    "The Mag'har",
    "Sporeggar",
    "The Consortium",
    "Ashtongue Deathsworn",
    "The Violet Eye",
]

# Hellfire dungeons give rep for Honor Hold (Alliance) or Thrallmar (Horde).
# We store both and resolve at runtime based on which faction the character has.
DUNGEON_REPUTATION_ALLIANCE = {
    "The Blood Furnace": "Honor Hold",
    "Hellfire Ramparts": "Honor Hold",
    "The Shattered Halls": "Honor Hold",
}
DUNGEON_REPUTATION_HORDE = {
    "The Blood Furnace": "Thrallmar",
    "Hellfire Ramparts": "Thrallmar",
    "The Shattered Halls": "Thrallmar",
}
DUNGEON_REPUTATION_NEUTRAL = {
    "The Slave Pens": "Cenarion Expedition",
    "The Underbog": "Cenarion Expedition",
    "The Steamvault": "Cenarion Expedition",
    "Mana-Tombs": "The Consortium",
    "Auchenai Crypts": "Lower City",
    "Sethekk Halls": "Lower City",
    "Shadow Labyrinth": "Lower City",
    "Old Hillsbrad Foothills": "Keepers of Time",
    "The Black Morass": "Keepers of Time",
    "The Mechanar": "The Sha'tar",
    "The Botanica": "The Sha'tar",
    "The Arcatraz": "The Sha'tar",
}

# Rep standing thresholds (total rep from start of that standing to cap)
REP_STANDING_ORDER = [
    "Hated",
    "Hostile",
    "Unfriendly",
    "Neutral",
    "Friendly",
    "Honored",
    "Revered",
    "Exalted",
]
REP_STANDING_THRESHOLDS = {
    "Hated": 36000,
    "Hostile": 3000,
    "Unfriendly": 3000,
    "Neutral": 3000,
    "Friendly": 6000,
    "Honored": 12000,
    "Revered": 21000,
    "Exalted": 999,
}

RAID_KEYWORDS = [
    # TBC
    "karazhan",
    "gruul",
    "magtheridon",
    "serpentshrine",
    "tempest keep",
    "hyjal",
    "black temple",
    "sunwell",
    "zul'aman",
    # WotLK
    "naxxramas",
    "obsidian sanctum",
    "eye of eternity",
    "ulduar",
    "trial of the crusader",
    "onyxia",
    "icecrown",
    "ruby sanctum",
    "vault of archavon",
]

# Map RAID_KEYWORDS substrings to soft-reserve config tags.
RAID_KEYWORD_TO_TAG = {
    "karazhan": "karazhan",
    "gruul": "gruuls-lair",
    "magtheridon": "magtheridons-lair",
    "serpentshrine": "serpentshrine-cavern",
    "tempest keep": "tempest-keep",
    "hyjal": "hyjal-summit",
    "black temple": "black-temple",
    "sunwell": "sunwell-plateau",
    "zul'aman": "zulaman",
    "naxxramas": "naxxramas",
    "obsidian sanctum": "obsidian-sanctum",
    "eye of eternity": "eye-of-eternity",
    "ulduar": "ulduar",
    "trial of the crusader": "trial-of-the-crusader",
    "onyxia": "onyxias-lair",
    "icecrown": "icecrown-citadel",
    "ruby sanctum": "ruby-sanctum",
    "vault of archavon": "vault-of-archavon",
}

# Pretty names for raid config tags.
RAID_TAG_PRETTY_NAMES = {
    "karazhan": "Karazhan",
    "gruuls-lair": "Gruul's Lair",
    "magtheridons-lair": "Magtheridon's Lair",
    "serpentshrine-cavern": "Serpentshrine Cavern",
    "tempest-keep": "Tempest Keep",
    "hyjal-summit": "Hyjal Summit",
    "black-temple": "Black Temple",
    "zulaman": "Zul'Aman",
    "sunwell-plateau": "Sunwell Plateau",
    "naxxramas": "Naxxramas",
    "obsidian-sanctum": "Obsidian Sanctum",
    "eye-of-eternity": "Eye of Eternity",
    "ulduar": "Ulduar",
    "trial-of-the-crusader": "Trial of the Crusader",
    "onyxias-lair": "Onyxia's Lair",
    "icecrown-citadel": "Icecrown Citadel",
    "ruby-sanctum": "Ruby Sanctum",
    "vault-of-archavon": "Vault of Archavon",
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


ALLIANCE_RACES = {"Human", "Dwarf", "Night Elf", "Gnome", "Draenei"}
HORDE_RACES = {"Orc", "Undead", "Tauren", "Troll", "Blood Elf"}


def build_dungeon_reputation(rep_lookup: dict, race: str = "") -> dict[str, str]:
    """Build dungeon-to-faction mapping, resolving Horde/Alliance for Hellfire."""
    result = dict(DUNGEON_REPUTATION_NEUTRAL)
    # Detect faction by rep data or race
    if "Honor Hold" in rep_lookup or race in ALLIANCE_RACES:
        result.update(DUNGEON_REPUTATION_ALLIANCE)
    elif "Thrallmar" in rep_lookup or race in HORDE_RACES:
        result.update(DUNGEON_REPUTATION_HORDE)
    else:
        result.update(DUNGEON_REPUTATION_ALLIANCE)
        result.update(DUNGEON_REPUTATION_HORDE)
    return result


def calc_rep_to_standing(
    current_standing: str, current_remaining: int, target_standing: str
) -> int | None:
    """Calculate total rep needed from current progress to reach target standing."""
    cur_idx = (
        REP_STANDING_ORDER.index(current_standing)
        if current_standing in REP_STANDING_ORDER
        else None
    )
    tgt_idx = (
        REP_STANDING_ORDER.index(target_standing)
        if target_standing in REP_STANDING_ORDER
        else None
    )
    if cur_idx is None or tgt_idx is None:
        return None
    if cur_idx >= tgt_idx:
        return 0  # Already at or past target
    # remaining in current tier + all intermediate tiers
    total = current_remaining
    for i in range(cur_idx + 1, tgt_idx):
        total += REP_STANDING_THRESHOLDS[REP_STANDING_ORDER[i]]
    return total


def extract_required_standing(source: str) -> str | None:
    """Extract the required reputation standing from a source string."""
    s = source.lower()
    if "exalted" in s:
        return "Exalted"
    if "revered" in s:
        return "Revered"
    if "honored" in s:
        return "Honored"
    return None


def sanitize_name(name: str) -> str:
    """Clean up item names that have embedded newlines/whitespace from parsing."""
    return " / ".join(part.strip() for part in name.split("\n") if part.strip())


# ---------------------------------------------------------------------------
# Item database helpers
# ---------------------------------------------------------------------------


def load_item_db() -> dict[int, dict]:
    """Load wowsims items.json into a dict keyed by item ID.

    Maps wowsims fields to the keys expected by format helpers:
    itemLevel, quality, subclass (armor type).
    """
    items_path = PROJECT_ROOT / "sources" / "wowsims-tbc" / "items.json"
    if not items_path.exists():
        return {}
    quality_map = {
        "Common": "Common",
        "Uncommon": "Uncommon",
        "Rare": "Rare",
        "Epic": "Epic",
        "Legendary": "Legendary",
    }
    items = json.loads(items_path.read_text(encoding="utf-8"))
    result: dict[int, dict] = {}
    for item in items:
        entry: dict = {
            "itemId": item["id"],
            "name": item["name"],
            "itemLevel": item.get("ilvl", 0),
            "quality": quality_map.get(
                item.get("quality", ""), item.get("quality", "")
            ),
        }
        if "armor_type" in item:
            entry["subclass"] = item["armor_type"]
        result[item["id"]] = entry
    return result


def format_ilvl_quality(item_info: dict | None) -> str:
    """Format ilvl and quality for display, e.g. 'ilvl 115 Epic'."""
    if not item_info:
        return ""
    ilvl = item_info.get("itemLevel", 0)
    quality = item_info.get("quality", "")
    return f"ilvl {ilvl} {quality}" if ilvl else ""


_preferred_armor = "Mail"  # Set at runtime based on spec


def format_armor_warning(item_info: dict | None) -> str:
    """Return a warning if an armor piece is not the spec's native type."""
    if not item_info:
        return ""
    subclass = item_info.get("subclass", "")
    armor_types = {"Cloth", "Leather", "Mail", "Plate"}
    if subclass in armor_types and subclass != _preferred_armor:
        return f" [{subclass}]"
    return ""


def format_item_extras(item_info: dict | None) -> str:
    """Build parenthesized suffix with ilvl and quality."""
    ilvl = format_ilvl_quality(item_info)
    return f"  ({ilvl})" if ilvl else ""


def format_rank_tag(upgrade: dict) -> str:
    """Format rank with Phase 0 only marker and future-phase longevity note."""
    p0 = " [Phase 0 only]" if upgrade.get("phase0_only") else ""
    next_rank = upgrade.get("next_phase_rank")
    if next_rank:
        future = f" + Future Phase {next_rank}"
    else:
        future = ""
    return f"{upgrade['rank']}{p0}{future}"


def format_rep_progress(rep_info: dict | None, required_standing: str | None) -> str:
    """Format rep progress toward a required standing."""
    if not required_standing or not rep_info:
        return ""
    total = calc_rep_to_standing(
        rep_info["standing"], rep_info["remainingRep"], required_standing
    )
    if total is not None and total > 0:
        return f"  -- need {required_standing}, ~{total:,} rep to go"
    if total == 0:
        return f"  -- need {required_standing}, READY TO BUY"
    return ""


# ---------------------------------------------------------------------------
# Source classification
# ---------------------------------------------------------------------------


_PROFESSION_KEYWORDS: dict[str, str] = {
    "tailoring": "Tailoring",
    "mooncloth tailoring": "Tailoring",
    "leatherworking": "Leatherworking",
    "tribal leatherworking": "Leatherworking",
    "dragonscale leatherworking": "Leatherworking",
    "blacksmithing": "Blacksmithing",
    "engineering": "Engineering",
    "jewelcrafting": "Jewelcrafting",
    "alchemy": "Alchemy",
    "enchanting": "Enchanting",
    "profession:": "Crafted",
}


def classify_source(source: str) -> list[str]:
    """Return tags like 'dungeon', 'heroic', 'reputation', 'profession', etc."""
    s = source.lower()

    if "world drop" in s:
        return ["world_drop"]
    if "world boss" in s:
        return ["world_boss"]
    if "classic -" in s or "classic\u2014" in s:
        return ["classic"]
    if "other (classic" in s:
        return ["classic"]
    if "arena" in s or "pvp" in s or "gladiator" in s:
        return ["pvp"]
    for kw, prof_name in _PROFESSION_KEYWORDS.items():
        if kw in s:
            return ["profession", f"profession:{prof_name}"]

    tags = []
    for faction in FACTION_NAMES:
        if faction.lower() in s:
            tags.append("reputation")
            break
    if not tags and ("exalted" in s or "revered" in s or "honored" in s):
        tags.append("reputation")

    if "heroic" in s or "(h)" in s:
        tags.append("heroic")
        if "dungeon" not in tags:
            tags.append("dungeon")
    elif "drop:" in s:
        if not any(rk in s for rk in RAID_KEYWORDS):
            tags.append("dungeon")
        else:
            tags.append("raid")

    if "quest:" in s:
        tags.append("quest")
    if (
        "badge of justice" in s
        or "badges of justice" in s
        or "badges" in s.split("(")[-1]
    ):
        tags.append("badges")
    if "vendor:" in s and "reputation" not in tags and "badges" not in tags:
        tags.append("vendor")
    if not tags:
        tags.append("other")
    return tags


def extract_faction(source: str) -> str | None:
    s_lower = source.lower()
    for faction in FACTION_NAMES:
        if faction.lower() in s_lower:
            return faction
    return None


def extract_dungeon(source: str, dungeon_reputation: dict) -> str | None:
    # Build a lookup that also matches without "The " prefix
    name_map: dict[str, str] = {}
    for key in dungeon_reputation:
        name_map[key] = key
        if key.startswith("The "):
            name_map[key.removeprefix("The ")] = key

    # Try last parenthesized group first — handles "Boss (H) (Instance)" format
    parens = re.findall(r"\(([^)]+)\)", source)
    for name in reversed(parens):
        if name in name_map:
            return name_map[name]
    # Also try "Heroic Instance" prefix stripping
    m = re.search(r"\((?:Heroic\s+)?(.+?)\)", source)
    if m:
        name = m.group(1)
        if name in name_map:
            return name_map[name]
    return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


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


def _normalize_wse(data: dict) -> dict:
    """Convert WowSims Exporter format to internal character format."""
    item_db = load_item_db()
    items = data.get("gear", {}).get("items", [])
    equipped: list[dict] = []
    for i, item in enumerate(items):
        if item is None or i >= len(WSE_SLOT_ORDER):
            continue
        item_id = item.get("id", 0)
        if not item_id:
            continue
        info = item_db.get(item_id)
        item_name = info["name"] if info else f"ID:{item_id}"
        equipped.append(
            {
                "slot": i + 1,
                "slotName": WSE_SLOT_ORDER[i],
                "itemId": item_id,
                "itemName": item_name,
            }
        )
    return {
        "name": data.get("name", "Unknown"),
        "class": data.get("class", ""),
        "race": data.get("race", ""),
        "equippedItems": equipped,
        "reputations": [],
    }


def load_character(path: str) -> dict:
    if path == "-":
        data = json.load(sys.stdin)
    else:
        p = Path(path)
        if not p.exists():
            alt = PROJECT_ROOT / "data" / p.name
            if alt.exists():
                p = alt
        data = json.loads(p.read_text(encoding="utf-8"))

    # Detect WSE format (has gear.items) vs old format (has character.equippedItems)
    if "gear" in data and "items" in data.get("gear", {}):
        return _normalize_wse(data)
    return data if "character" not in data else data["character"]


def pretty_phase(phase_key: str) -> str:
    """Convert 'phase-1' to 'Phase 1' for display."""
    m = re.match(r"phase-(\d+)", phase_key)
    return f"Phase {m.group(1)}" if m else phase_key


def load_soft_reserves(
    path: Path | None = None,
) -> tuple[dict[str, int], dict[str, str]]:
    """Load soft-reserve config from data/soft-reserves.txt.

    Returns (sr_counts, sr_groups):
      sr_counts: raid-tag -> SR count  (each tag in a group gets the count)
      sr_groups: raid-tag -> group key  (e.g. "gruuls-lair" -> "gruuls-lair+magtheridons-lair")
    """
    if path is None:
        path = PROJECT_ROOT / "data" / "soft-reserves.txt"
    if not path.exists():
        return {}, {}

    sr_counts: dict[str, int] = {}
    sr_groups: dict[str, str] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val_raw = val.partition("#")[0].strip()
        try:
            count = int(val_raw)
        except ValueError:
            print(
                f"Error: invalid value '{val_raw}' in soft-reserves.txt "
                f"(expected integer) on line: {line}",
                file=sys.stderr,
            )
            sys.exit(1)
        if count < 0:
            print(
                f"Error: negative SR count '{count}' in soft-reserves.txt "
                f"on line: {line}",
                file=sys.stderr,
            )
            sys.exit(1)
        tags = [t.strip() for t in key.split("+")]

        for tag in tags:
            if tag in sr_counts:
                print(
                    f"Error: raid tag '{tag}' appears multiple times in "
                    f"soft-reserves.txt (check for duplicate or conflicting groups)",
                    file=sys.stderr,
                )
                sys.exit(1)
            sr_counts[tag] = count
            sr_groups[tag] = key

    return sr_counts, sr_groups


def match_raid_tag(source: str) -> str | None:
    """Map a source string to a soft-reserve config tag.

    E.g. "Drop: Prince Malchezaar (Karazhan)" -> "karazhan"
    """
    s = source.lower()
    for keyword, tag in RAID_KEYWORD_TO_TAG.items():
        if keyword in s:
            return tag
    return None


# ---------------------------------------------------------------------------
# BiS slot resolution and ranking
# ---------------------------------------------------------------------------


def resolve_slot_key(bis_slot: str, phase_data: dict) -> str:
    """Handle slot name variance across specs/phases."""
    if bis_slot in phase_data:
        return bis_slot
    # Relic slot: totems / idols / librams
    if bis_slot in ("totems", "idols", "librams"):
        for alt in ("totems", "idols", "librams"):
            if alt in phase_data:
                return alt
    # Off-hand slot: offhands / shields-offhands / shields
    if bis_slot in ("offhands", "shields-offhands", "shields"):
        for alt in ("offhands", "shields-offhands", "shields"):
            if alt in phase_data:
                return alt
    # Shoulder slot: shoulders / shoulder
    if bis_slot in ("shoulders", "shoulder"):
        for alt in ("shoulders", "shoulder"):
            if alt in phase_data:
                return alt
    return bis_slot


def lookup_item_rank(item_id: int, bis_slot: str, phase_data: dict) -> str | None:
    """Find an item's rank (BiS/Option/PvP) in a single phase's data."""
    slot_key = resolve_slot_key(bis_slot, phase_data)
    for bis_item in phase_data.get(slot_key, []):
        if bis_item.get("item_id") == item_id:
            return bis_item["rank"]
    return None


def get_effective_rank(
    item_id: int,
    bis_slot: str,
    current_phase_data: dict,
    phase0_data: dict,
    current_phase: str,
):
    """
    Determine an item's effective rank using phase priority:
    1. If listed in current phase -> use that rank & phase
    2. Else if listed in phase-0 -> use that rank, note it's phase-0 only
    3. Else -> not on any list
    Returns (rank, phase, phase0_only)
    """
    if current_phase != "phase-0":
        rank = lookup_item_rank(item_id, bis_slot, current_phase_data)
        if rank:
            return rank, current_phase, False

    rank = lookup_item_rank(item_id, bis_slot, phase0_data)
    if rank:
        return rank, "phase-0", current_phase != "phase-0"

    return None, None, False


def score_upgrade(
    rank: str,
    phase: str,
    current_phase: str,
    next_phase_rank: str | None = None,
) -> float:
    """
    Score an upgrade on a 100-point scale with phase decay and longevity bonus.

    Base scores (current phase):
      BiS:    100  (1.0x multiplier)
      Option:  80  (0.8x multiplier)

    Each phase behind current halves the base score:
      1 phase behind: 0.5x  -> BiS=50, Option=40
      2 phases behind: 0.25x -> BiS=25, Option=20
      etc.

    Longevity bonus: if the item also appears in the next phase's BiS list,
    it stays relevant longer and gets a significant bonus:
      Still BiS next phase:    +50  (half the BiS base — huge)
      Still Option next phase: +30
    """
    cur_num = int(current_phase.split("-")[1]) if "-" in current_phase else 0
    item_num = int(phase.split("-")[1]) if "-" in phase else 0

    phases_behind = max(0, cur_num - item_num)
    decay = 0.5**phases_behind

    base = 100 if rank == "BiS" else 80
    score = base * decay

    if next_phase_rank == "BiS":
        score += 50
    elif next_phase_rank == "Option":
        score += 30

    return score


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def categorize_equipped(
    equipped_by_slot: dict[str, list[dict]],
    all_equipped_ids: set[int],
    bis_data: dict,
    current_phase: str,
    current_phase_data: dict,
    phase0_data: dict,
    phases_to_check: list[str],
    dungeon_reputation: dict[str, str],
    rep_lookup: dict,
    item_db: dict[int, dict],
    allowed_tags: set[str] | None = None,
):
    """Categorize each equipped item into tiers and find available upgrades."""
    current_bis: list[tuple[str, str, str, str]] = []
    current_option: list[tuple[str, str, str, str]] = []
    old_bis: list[tuple[str, str, str, str]] = []
    old_option: list[tuple[str, str, str, str]] = []
    not_listed_slots: list[tuple[str, str, str, str]] = []
    all_upgrades: list[dict] = []
    no_upgrade_slots: list[tuple[str, str, str, str]] = []

    for bis_slot, items in equipped_by_slot.items():
        for eq_item in items:
            item_id = eq_item["itemId"]
            item_name = eq_item["itemName"]
            slot_label = eq_item["slotName"]

            # Determine equipped item's rank with phase priority
            eq_rank, eq_phase, eq_p0_only = get_effective_rank(
                item_id, bis_slot, current_phase_data, phase0_data, current_phase
            )

            # Look up equipped item in item DB for enrichment
            eq_info = item_db.get(item_id)
            eq_extras = format_item_extras(eq_info)
            eq_armor = format_armor_warning(eq_info)

            # Build display tuple: (slot, name, armor_warning, extras)
            eq_display = (slot_label, item_name, eq_armor, eq_extras)

            # Classify into tier
            if eq_rank == "BiS" and not eq_p0_only:
                current_bis.append(eq_display)
                continue
            elif eq_rank == "Option" and not eq_p0_only:
                current_option.append(eq_display)
            elif eq_rank == "BiS" and eq_p0_only:
                old_bis.append(eq_display)
            elif eq_rank == "Option" and eq_p0_only:
                old_option.append(eq_display)
            elif eq_rank == "PvP":
                if eq_p0_only:
                    old_option.append(eq_display)
                else:
                    current_option.append(eq_display)
            else:
                not_listed_slots.append(eq_display)

            # Find upgrades from dungeons/reps/badges for this slot
            slot_upgrades = _find_slot_upgrades(
                bis_slot,
                slot_label,
                item_id,
                item_name,
                eq_rank,
                eq_info,
                all_equipped_ids,
                bis_data,
                current_phase,
                current_phase_data,
                phase0_data,
                phases_to_check,
                dungeon_reputation,
                rep_lookup,
                item_db,
                allowed_tags,
            )
            all_upgrades.extend(slot_upgrades)

            if not slot_upgrades:
                no_upgrade_slots.append(
                    (slot_label, item_name, eq_rank or "Not on list", eq_extras)
                )

    return (
        current_bis,
        current_option,
        old_bis,
        old_option,
        not_listed_slots,
        all_upgrades,
        no_upgrade_slots,
    )


def _find_slot_upgrades(
    bis_slot: str,
    slot_label: str,
    item_id: int,
    item_name: str,
    eq_rank: str | None,
    eq_info: dict | None,
    all_equipped_ids: set[int],
    bis_data: dict,
    current_phase: str,
    current_phase_data: dict,
    phase0_data: dict,
    phases_to_check: list[str],
    dungeon_reputation: dict[str, str],
    rep_lookup: dict,
    item_db: dict[int, dict],
    allowed_tags: set[str] | None = None,
) -> list[dict]:
    """Find all dungeon/rep/badge/raid upgrades for a single equipped slot."""
    if allowed_tags is None:
        allowed_tags = {"dungeon", "heroic", "reputation", "badges", "raid", "pvp"}
    slot_upgrades: list[dict] = []
    seen_item_ids: set[int] = set()

    for phase in phases_to_check:
        phase_data = bis_data["phases"].get(phase, {})
        slot_key = resolve_slot_key(bis_slot, phase_data)
        slot_items = phase_data.get(slot_key, [])

        # Find the equipped item's position in this slot's list.
        # Only suggest items ranked higher (earlier in the list).
        equipped_pos = None
        for idx, si in enumerate(slot_items):
            if si.get("item_id") == item_id:
                equipped_pos = idx
                break

        for idx, bis_item in enumerate(slot_items):
            bis_id = bis_item.get("item_id")
            if bis_id == item_id or bis_id in seen_item_ids:
                continue
            if bis_id in all_equipped_ids:
                continue
            # Skip items ranked lower than the equipped item in the list
            if equipped_pos is not None and idx >= equipped_pos:
                continue

            up_rank, up_phase, up_p0_only = get_effective_rank(
                bis_id, bis_slot, current_phase_data, phase0_data, current_phase
            )
            if not up_rank:
                continue

            source = bis_item.get("source", "")
            tags = classify_source(source)
            if not any(t in allowed_tags for t in tags):
                continue

            seen_item_ids.add(bis_id)
            faction = extract_faction(source)
            rep_info = rep_lookup.get(faction) if faction else None
            dungeon = extract_dungeon(source, dungeon_reputation)

            # Check if item appears in the next phase for longevity bonus
            cur_num = int(current_phase.split("-")[1]) if "-" in current_phase else 0
            next_phase_key = f"phase-{cur_num + 1}"
            next_phase_data = bis_data["phases"].get(next_phase_key, {})
            next_phase_rank = lookup_item_rank(bis_id, bis_slot, next_phase_data)

            item_score = score_upgrade(
                up_rank, up_phase, current_phase, next_phase_rank
            )
            required_standing = extract_required_standing(source)

            upgrade = {
                "name": sanitize_name(bis_item["name"]),
                "item_id": bis_id,
                "rank": up_rank,
                "phase": up_phase,
                "phase0_only": up_p0_only,
                "next_phase_rank": next_phase_rank,
                "source": source,
                "tags": tags,
                "faction": faction,
                "rep_info": rep_info,
                "required_standing": required_standing,
                "dungeon": dungeon,
                "slot": slot_label,
                "current_item": item_name,
                "current_rank": eq_rank or "Not on list",
                "score": item_score,
                "item_info": item_db.get(bis_id),
                "current_item_info": eq_info,
            }
            slot_upgrades.append(upgrade)

    return slot_upgrades


def build_dungeon_priority(
    deduped_upgrades: list[dict],
    dungeon_reputation: dict[str, str],
    rep_needs: dict[str, list[dict]],
    rep_lookup: dict,
    badge_bonus: int,
) -> list[dict]:
    """Build and score dungeon priority list."""
    dungeon_actions: dict[str, dict] = {}

    for up in deduped_upgrades:
        if "dungeon" not in up["tags"]:
            continue
        dungeon = up["dungeon"]
        if not dungeon:
            continue

        is_heroic = "heroic" in up["tags"]
        key = f"Heroic {dungeon}" if is_heroic else dungeon

        if key not in dungeon_actions:
            dungeon_actions[key] = {
                "key": key,
                "dungeon": dungeon,
                "heroic": is_heroic,
                "drops": [],
                "score": 0,
                "score_breakdown": [],
                "rep_faction": dungeon_reputation.get(dungeon),
                "rep_vendor_items": [],
                "badges": is_heroic,
            }

        entry = dungeon_actions[key]
        entry["drops"].append(up)
        entry["score"] += up["score"]
        entry["score_breakdown"].append(
            f"{format_rank_tag(up)} drop: +{up['score']:.0f}"
        )

    # Add rep synergy scoring
    for entry in dungeon_actions.values():
        faction = entry["rep_faction"]
        if faction and faction in rep_needs:
            entry["rep_vendor_items"] = rep_needs[faction]
            rep_score = sum(vi["score"] for vi in rep_needs[faction])
            entry["score"] += rep_score
            entry["score_breakdown"].append(
                f"rep toward {faction} vendor items: +{rep_score:.0f}"
            )
        if entry["badges"] and badge_bonus > 0:
            entry["score"] += badge_bonus
            entry["score_breakdown"].append(
                f"badges toward vendor items: +{badge_bonus}"
            )

    # Merge normal drops into heroic entries (heroic runs drop both)
    # and create heroic entries for normal-only dungeons with rep synergy
    for entry in list(dungeon_actions.values()):
        if entry["heroic"]:
            continue
        heroic_key = f"Heroic {entry['dungeon']}"
        if heroic_key in dungeon_actions:
            # Heroic entry exists — merge normal drops into it
            heroic_entry = dungeon_actions[heroic_key]
            heroic_drop_ids = {d["item_id"] for d in heroic_entry["drops"]}
            for drop in entry["drops"]:
                if drop["item_id"] not in heroic_drop_ids:
                    heroic_entry["drops"].append(drop)
                    heroic_entry["score"] += drop["score"]
                    heroic_entry["score_breakdown"].append(
                        f"{format_rank_tag(drop)} drop: +{drop['score']:.0f}"
                    )
        else:
            # No heroic entry — create one if there's rep synergy
            faction = entry["rep_faction"]
            if faction and faction in rep_needs:
                heroic_entry = {
                    "key": heroic_key,
                    "dungeon": entry["dungeon"],
                    "heroic": True,
                    "drops": list(entry["drops"]),
                    "score": entry["score"] + badge_bonus,
                    "score_breakdown": list(entry["score_breakdown"])
                    + (
                        [f"badges toward vendor items: +{badge_bonus}"]
                        if badge_bonus > 0
                        else []
                    ),
                    "rep_faction": faction,
                    "rep_vendor_items": rep_needs[faction],
                    "badges": True,
                }
                dungeon_actions[heroic_key] = heroic_entry

    return sorted(dungeon_actions.values(), key=lambda x: x["score"], reverse=True)


def build_rep_actions(
    rep_needs: dict[str, list[dict]],
    rep_lookup: dict,
    dungeon_reputation: dict[str, str],
) -> list[dict]:
    """Build reputation goal actions."""
    rep_actions = []
    for faction, items in rep_needs.items():
        rep_info = rep_lookup.get(faction)
        if not rep_info:
            continue
        dungeons_for_rep = [d for d, f in dungeon_reputation.items() if f == faction]
        total_score = sum(i["score"] for i in items)
        rep_actions.append(
            {
                "faction": faction,
                "items": items,
                "rep_info": rep_info,
                "dungeons_for_rep": dungeons_for_rep,
                "score": total_score,
            }
        )
    return sorted(rep_actions, key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_equipped_section(
    title: str,
    items: list[tuple[str, str, str, str]],
    suffix_fn=None,
):
    """Print an equipped item tier section (BiS, Option, Phase 0, Not listed)."""
    if not items:
        return
    print(f"=== {title} ===")
    for slot, name, armor, extras in items:
        suffix = suffix_fn(slot, name) if suffix_fn else ""
        print(f"  {slot:12s}  {name}{armor}{extras}{suffix}")
    print()


def print_dungeon_priority(sorted_dungeons: list[dict], rep_lookup: dict):
    """Print the dungeon priority ranking."""
    if not sorted_dungeons:
        return
    print("=== PRIORITY: DUNGEONS TO RUN (ranked by value per run) ===")
    for i, entry in enumerate(sorted_dungeons, 1):
        badge_tag = " +badges" if entry["badges"] else ""
        rep_tag = ""
        if entry["rep_faction"]:
            ri = rep_lookup.get(entry["rep_faction"])
            if ri:
                rep_tag = f" +{entry['rep_faction']} rep (You: {ri['standing']}, {ri['remainingRep']:,} to next tier)"
            else:
                rep_tag = f" +{entry['rep_faction']} rep"

        print(
            f"\n  #{i}  {entry['key']}  (score: {entry['score']:.0f}){badge_tag}{rep_tag}"
        )
        print(f"       Score: {' | '.join(entry['score_breakdown'])}")

        for drop in entry["drops"]:
            rank_tag = format_rank_tag(drop)
            armor = format_armor_warning(drop.get("item_info"))
            extra = format_item_extras(drop.get("item_info"))
            cur_extra = format_item_extras(drop.get("current_item_info"))
            print(
                f"       [{rank_tag:16s}]  {drop['name']}{armor}{extra}  ({drop['slot']} -- replaces {drop['current_item']}{cur_extra})"
            )

        if entry["rep_vendor_items"]:
            print("       Also earns rep toward:")
            for vi in entry["rep_vendor_items"]:
                rank_tag = format_rank_tag(vi)
                armor = format_armor_warning(vi.get("item_info"))
                extra = format_item_extras(vi.get("item_info"))
                print(
                    f"         [{rank_tag:16s}]  {vi['name']}{armor}{extra}  ({vi['slot']})"
                )
    print()


def print_rep_goals(sorted_rep: list[dict]):
    """Print reputation goals section."""
    if not sorted_rep:
        return
    print("=== REPUTATION GOALS ===")
    for entry in sorted_rep:
        ri = entry["rep_info"]
        print(
            f"\n  {entry['faction']}  (You: {ri['standing']}, {ri['remainingRep']:,} rep to next tier)"
        )
        for item in entry["items"]:
            rank_tag = format_rank_tag(item)
            armor = format_armor_warning(item.get("item_info"))
            extra = format_item_extras(item.get("item_info"))
            rep_prog = format_rep_progress(ri, item.get("required_standing"))
            print(
                f"    [{rank_tag:16s}]  {item['name']}{armor}{extra}  ({item['slot']} -- replaces {item['current_item']}){rep_prog}"
            )
        if entry["dungeons_for_rep"]:
            print(f"    Grind via: {', '.join(entry['dungeons_for_rep'])}")
    print()


def print_slot_breakdown(all_upgrades: list[dict]):
    """Print per-slot upgrade breakdown."""
    slot_groups: dict[str, list[dict]] = defaultdict(list)
    for up in all_upgrades:
        slot_groups[up["slot"]].append(up)

    if not slot_groups:
        return
    print("=== ALL UPGRADES BY SLOT ===")
    for slot in dict.fromkeys(up["slot"] for up in all_upgrades):
        items_in_slot = slot_groups[slot]
        current = items_in_slot[0]["current_item"]
        current_rank = items_in_slot[0]["current_rank"]
        cur_armor = format_armor_warning(items_in_slot[0].get("current_item_info"))
        cur_extra = format_item_extras(items_in_slot[0].get("current_item_info"))
        rank_note = f" [{current_rank}]" if current_rank != "Not on list" else ""
        print(f"\n  {slot}: {current}{cur_armor}{rank_note}{cur_extra}")
        for up in items_in_slot:
            heroic = " (H)" if "heroic" in up["tags"] else ""
            rank_label = f"[{format_rank_tag(up)}]"
            armor = format_armor_warning(up.get("item_info"))
            extra = format_item_extras(up.get("item_info"))
            line = f"    {rank_label:18s} {up['name']}{armor}{extra}{heroic}  --  {up['source']}"
            if up["rep_info"]:
                ri = up["rep_info"]
                req = up.get("required_standing")
                rep_prog = format_rep_progress(ri, req)
                if rep_prog:
                    line += f"  ({rep_prog.strip(' -')})"
                else:
                    line += f"  (You: {ri['standing']} -- {ri['remainingRep']:,} rep to next tier)"
            print(line)
    print()


def print_raid_upgrades(
    raid_upgrades: list[dict],
    sr_counts: dict[str, int],
    sr_groups: dict[str, str],
):
    """Print raid upgrades grouped by raid instance with soft-reserve info."""
    if not raid_upgrades:
        return

    # Group by SR group key (so grouped raids like Gruul+Mag appear together)
    group_items: dict[str, list[dict]] = defaultdict(list)
    for up in raid_upgrades:
        tag = match_raid_tag(up["source"])
        if tag:
            group_key = sr_groups.get(tag, tag)
            group_items[group_key].append(up)
        else:
            group_items["unknown"].append(up)

    # Deduplicate: show each item once (highest-score slot wins for shared slots)
    seen_ids: set[int] = set()
    for group_key in group_items:
        deduped: list[dict] = []
        for up in group_items[group_key]:
            if up["item_id"] not in seen_ids:
                seen_ids.add(up["item_id"])
                deduped.append(up)
        group_items[group_key] = deduped

    # Emit all unknown-source warnings to stderr upfront
    if "unknown" in group_items:
        for up in group_items["unknown"]:
            print(
                f"WARNING: unrecognized raid source: {up['source']}",
                file=sys.stderr,
            )

    print("=== RAID UPGRADES ===")
    for group_key, items in group_items.items():
        if not items:
            continue
        if group_key == "unknown":
            print("\n  Unknown Raid  (SR: unknown)")
            items.sort(key=lambda x: x["score"], reverse=True)
            for up in items:
                rank_label = f"[{format_rank_tag(up)}]"
                armor = format_armor_warning(up.get("item_info"))
                extra = format_item_extras(up.get("item_info"))
                print(
                    f"    {rank_label:18s} {up['name']}{armor}{extra}  "
                    f"({up['slot']} -- replaces {up['current_item']})  --  {up['source']}"
                )
            continue

        # Build pretty header from group key
        tags = [t.strip() for t in group_key.split("+")]
        pretty_names = [RAID_TAG_PRETTY_NAMES.get(t, t) for t in tags]
        header = " + ".join(pretty_names)

        # SR info from the first tag in the group (all share the same count)
        sr_count = sr_counts.get(tags[0], 0)
        if sr_count == 0:
            sr_label = "master looter"
        elif sr_count == 1:
            sr_label = "1 soft reserve"
        else:
            sr_label = f"{sr_count} soft reserves"

        print(f"\n  {header}  ({sr_label})")

        # Sort by score descending within each raid group
        items.sort(key=lambda x: x["score"], reverse=True)
        for up in items:
            rank_label = f"[{format_rank_tag(up)}]"
            armor = format_armor_warning(up.get("item_info"))
            extra = format_item_extras(up.get("item_info"))
            print(
                f"    {rank_label:18s} {up['name']}{armor}{extra}  "
                f"({up['slot']} -- replaces {up['current_item']})  --  {up['source']}"
            )
    print()


def print_no_upgrade(no_upgrade_slots: list[tuple[str, str, str, str]]):
    """Print slots with no dungeon/rep/raid upgrade available."""
    if not no_upgrade_slots:
        return
    print("=== NO DUNGEON/REP/RAID UPGRADE (craft or world boss needed) ===")
    for slot, name, rank, extras in no_upgrade_slots:
        print(f"  {slot:12s}  {name} [{rank}]{extras}")
    print()


def print_summary(
    cp: str,
    current_bis: list,
    current_option: list,
    old_bis: list,
    old_option: list,
    not_listed_slots: list,
    dungeon_upgrades: list,
    raid_upgrades: list,
    no_upgrade_slots: list,
):
    """Print the summary section."""
    dungeon_slot_count = (
        len({up["slot"] for up in dungeon_upgrades}) if dungeon_upgrades else 0
    )
    raid_slot_count = len({up["slot"] for up in raid_upgrades}) if raid_upgrades else 0
    total = (
        len(current_bis)
        + len(current_option)
        + len(old_bis)
        + len(old_option)
        + len(not_listed_slots)
    )
    print(f"Summary: {total} slots total")
    print(f"  {cp} BiS: {len(current_bis)}")
    print(f"  {cp} Option: {len(current_option)}")
    if old_bis or old_option:
        print(f"  Phase 0 only (outdated): {len(old_bis) + len(old_option)}")
    if not_listed_slots:
        print(f"  Not on any list: {len(not_listed_slots)}")
    if dungeon_slot_count:
        print(f"  Slots with dungeon/rep upgrades: {dungeon_slot_count}")
    if raid_slot_count:
        print(f"  Slots with raid upgrades: {raid_slot_count}")
    if no_upgrade_slots:
        print(f"  Slots needing craft/other: {len(no_upgrade_slots)}")


# ---------------------------------------------------------------------------
# Spec resolution
# ---------------------------------------------------------------------------

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

# Preferred armor type per spec (for armor warnings)
_SPEC_ARMOR: dict[str, str] = {
    "resto-shaman": "Mail",
    "elemental-shaman": "Mail",
    "prot-paladin": "Plate",
}


def resolve_spec(raw: str) -> str:
    key = raw.strip().lower()
    if key not in _SPEC_ALIASES:
        print(f"Unknown spec '{raw}'. Use: resto, ele, prot.")
        sys.exit(1)
    return _SPEC_ALIASES[key]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Compare equipped gear against BiS lists.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  bis-gear --spec resto\n"
            "  bis-gear --spec ele\n"
            "  bis-gear --spec resto custom.json\n"
            "  echo '{...}' | bis-gear --spec ele -"
        ),
    )
    parser.add_argument(
        "--spec",
        required=True,
        help="Spec to check: resto, ele (or elemental).",
    )
    parser.add_argument(
        "character_file",
        nargs="?",
        default=None,
        help="Path to character JSON (or '-' for stdin). Defaults to data/{spec}.json.",
    )
    parser.add_argument(
        "--include-deferred",
        action="store_true",
        help="Include deferred sources (PvP, classic raids) in upgrade list.",
    )
    args = parser.parse_args()

    spec = resolve_spec(args.spec)
    global _preferred_armor
    _preferred_armor = _SPEC_ARMOR.get(spec, "Mail")
    # Derive default character file name from spec slug
    # resto-shaman → resto.json, prot-paladin → prot-paladin.json
    _default_char_files: dict[str, str] = {
        "resto-shaman": "resto.json",
        "elemental-shaman": "elemental.json",
        "prot-paladin": "prot-paladin.json",
    }
    default_char_file = _default_char_files.get(spec, spec + ".json")
    char_path = (
        args.character_file if args.character_file is not None else default_char_file
    )

    char = load_character(char_path)
    equipped = char.get("equippedItems", [])
    reputations_raw = char.get("reputations", [])

    # Build set of allowed source tags based on character professions + flags
    char_professions = {p["name"] for p in char.get("professions", [])}
    # Default allowed tags (rep/badge vendors are tagged separately, not as "vendor")
    allowed_tags = {
        "dungeon",
        "heroic",
        "reputation",
        "badges",
        "raid",
        "world_drop",
        "world_boss",
        "quest",
    }
    # Add profession tags for professions the character actually has
    for prof_name in char_professions:
        allowed_tags.add(f"profession:{prof_name}")
    # Generic "Crafted" tag also allowed if character has ANY crafting profession
    crafting_professions = {
        "Tailoring",
        "Leatherworking",
        "Blacksmithing",
        "Engineering",
        "Jewelcrafting",
        "Alchemy",
        "Enchanting",
    }
    if char_professions & crafting_professions:
        allowed_tags.add("profession:Crafted")
    if args.include_deferred:
        allowed_tags.update(
            {"pvp", "classic", "other", "profession", "profession:Crafted"}
        )
        # Include all profession tags when deferred
        for prof_name in crafting_professions:
            allowed_tags.add(f"profession:{prof_name}")

    # Flatten reputations
    rep_lookup: dict[str, dict] = {}
    for group in reputations_raw:
        for faction in group.get("factions", []):
            rep_lookup[faction["name"]] = faction

    # Build faction-aware dungeon rep mapping
    dungeon_reputation = build_dungeon_reputation(rep_lookup, char.get("race", ""))

    # Load item database for enrichment
    item_db = load_item_db()

    # Load soft-reserve config
    sr_counts, sr_groups = load_soft_reserves()

    # Load BiS data — merge items across all sources, dedup by item_id per slot.
    # If an item appears in multiple sources, keep the best rank (BiS > Option).
    bis_data: dict = {"phases": {}}
    _rank_priority = {"BiS": 0, "Option": 1}
    for src_name in ("al_bis_gear.json", "wtbc_bis_gear.json"):
        src_path = PROJECT_ROOT / "output" / spec / src_name
        if not src_path.exists():
            continue
        src_data = json.loads(src_path.read_text(encoding="utf-8"))
        for phase_key, phase_slots in src_data.get("phases", {}).items():
            if phase_key not in bis_data["phases"]:
                bis_data["phases"][phase_key] = {}
            for slot_key, items in phase_slots.items():
                if slot_key not in bis_data["phases"][phase_key]:
                    bis_data["phases"][phase_key][slot_key] = []
                existing = bis_data["phases"][phase_key][slot_key]
                seen_ids = {it["item_id"] for it in existing}
                for item in items:
                    iid = item.get("item_id")
                    if iid in seen_ids:
                        # Upgrade rank if this source ranks it higher
                        for ex in existing:
                            if ex["item_id"] == iid:
                                if _rank_priority.get(
                                    item.get("rank"), 9
                                ) < _rank_priority.get(ex.get("rank"), 9):
                                    ex["rank"] = item["rank"]
                                break
                    else:
                        existing.append(item)
                        seen_ids.add(iid)
    if not bis_data["phases"]:
        print(
            f"No BiS data found in {PROJECT_ROOT / 'output' / spec}. "
            f"Expected al_bis_gear.json or wtbc_bis_gear.json."
        )
        sys.exit(1)
    current_phase = (
        (PROJECT_ROOT / "data" / "current-phase.txt")
        .read_text(encoding="utf-8")
        .strip()
    )
    phases_to_check = (
        ["phase-0", current_phase] if current_phase != "phase-0" else ["phase-0"]
    )

    current_phase_data = bis_data["phases"].get(current_phase, {})
    phase0_data = bis_data["phases"].get("phase-0", {})

    # Build equipped lookup
    equipped_by_slot: dict[str, list[dict]] = {}
    for item in equipped:
        bis_slot = SLOT_MAP.get(item["slotName"])
        if bis_slot:
            equipped_by_slot.setdefault(bis_slot, []).append(item)

    all_equipped_ids = {item["itemId"] for item in equipped}

    # Categorize equipped items and find upgrades
    (
        current_bis,
        current_option,
        old_bis,
        old_option,
        not_listed_slots,
        all_upgrades,
        no_upgrade_slots,
    ) = categorize_equipped(
        equipped_by_slot,
        all_equipped_ids,
        bis_data,
        current_phase,
        current_phase_data,
        phase0_data,
        phases_to_check,
        dungeon_reputation,
        rep_lookup,
        item_db,
        allowed_tags,
    )

    # Split upgrades into dungeon/rep/badge vs raid
    dungeon_upgrades_all = [up for up in all_upgrades if "raid" not in up["tags"]]
    raid_upgrades_all = [up for up in all_upgrades if "raid" in up["tags"]]

    # Deduplicate ring/trinket upgrades for scoring (dungeon/rep/badge only)
    scored_item_ids: set[int] = set()
    deduped_upgrades: list[dict] = []
    for up in dungeon_upgrades_all:
        if up["item_id"] not in scored_item_ids:
            scored_item_ids.add(up["item_id"])
            deduped_upgrades.append(up)

    # Collect reputation needs (deduplicated)
    rep_needs: dict[str, list[dict]] = defaultdict(list)
    rep_needs_seen: dict[str, set] = defaultdict(set)
    for up in deduped_upgrades:
        if "reputation" in up["tags"] and up["faction"]:
            if up["item_id"] not in rep_needs_seen[up["faction"]]:
                rep_needs_seen[up["faction"]].add(up["item_id"])
                rep_needs[up["faction"]].append(up)

    # Compute badge bonus once
    badge_items = [u for u in deduped_upgrades if "badges" in u["tags"]]
    badge_bonus = (
        round(sum(b["score"] for b in badge_items) * 0.1) if badge_items else 0
    )

    # Build priority lists
    sorted_dungeons = build_dungeon_priority(
        deduped_upgrades, dungeon_reputation, rep_needs, rep_lookup, badge_bonus
    )
    sorted_rep = build_rep_actions(rep_needs, rep_lookup, dungeon_reputation)

    # --- Output ---
    cp = pretty_phase(current_phase)
    print(
        f"Character: {char.get('name', '?')} ({char.get('class', '?')}) "
        f"-- Checking against: {', '.join(pretty_phase(p) for p in phases_to_check)}"
    )
    print(f"   Current phase: {cp} (authoritative) | Phase 0 (fallback)\n")

    print_equipped_section(f"{cp.upper()} BIS (you're set)", current_bis)
    print_equipped_section(
        f"{cp.upper()} OPTION (upgrade available this phase)", current_option
    )
    if old_bis or old_option:
        print_equipped_section(
            f"PHASE 0 ONLY (not in {cp} list -- outdated)",
            old_bis + old_option,
            suffix_fn=lambda s, n: (
                "  [was Phase 0 BiS]"
                if (s, n) in {(x[0], x[1]) for x in old_bis}
                else "  [was Phase 0 Option]"
            ),
        )
    print_equipped_section("NOT ON ANY BIS LIST", not_listed_slots)

    print_dungeon_priority(sorted_dungeons, rep_lookup)
    print_rep_goals(sorted_rep)
    print_slot_breakdown(dungeon_upgrades_all)
    print_raid_upgrades(raid_upgrades_all, sr_counts, sr_groups)
    print_no_upgrade(no_upgrade_slots)
    print_summary(
        cp,
        current_bis,
        current_option,
        old_bis,
        old_option,
        not_listed_slots,
        dungeon_upgrades_all,
        raid_upgrades_all,
        no_upgrade_slots,
    )


if __name__ == "__main__":
    main()
