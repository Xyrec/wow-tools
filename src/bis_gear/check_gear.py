"""
Compare equipped gear against Phase 0 and current-phase BiS lists.

Priority: current phase is authoritative. Phase 0 is only consulted as a
fallback when an item or upgrade doesn't appear in the current phase at all.

Usage:
    bis-gear character.json
    bis-gear -                    # read from stdin
    python -m bis_gear character.json

Reads current-phase.txt and bis_gear.json from the project data directory.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Project root is two levels up from src/bis_gear/
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Map WoW API slot names to bis_gear.json slot keys.
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
    "karazhan",
    "gruul",
    "magtheridon",
    "serpentshrine",
    "tempest keep",
    "hyjal",
    "black temple",
    "sunwell",
    "zul'aman",
    "naxxramas",
    "ahn'qiraj",
]


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def build_dungeon_reputation(rep_lookup: dict) -> dict[str, str]:
    """Build dungeon-to-faction mapping, resolving Horde/Alliance for Hellfire."""
    result = dict(DUNGEON_REPUTATION_NEUTRAL)
    # Detect faction by checking which rep the character has
    if "Honor Hold" in rep_lookup:
        result.update(DUNGEON_REPUTATION_ALLIANCE)
    elif "Thrallmar" in rep_lookup:
        result.update(DUNGEON_REPUTATION_HORDE)
    else:
        # Fallback: include both, whichever matches will work
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
    """Load items.json into a dict keyed by itemId for O(1) lookups."""
    items_path = PROJECT_ROOT / "sources" / "item-data" / "items.json"
    if not items_path.exists():
        return {}
    items = json.loads(items_path.read_text(encoding="utf-8"))
    return {item["itemId"]: item for item in items}


def format_ilvl_quality(item_info: dict | None) -> str:
    """Format ilvl and quality for display, e.g. 'ilvl 115 Epic'."""
    if not item_info:
        return ""
    ilvl = item_info.get("itemLevel", 0)
    quality = item_info.get("quality", "")
    return f"ilvl {ilvl} {quality}" if ilvl else ""


def format_armor_warning(item_info: dict | None) -> str:
    """Return a warning if an armor piece is not Mail (Shaman's native type)."""
    if not item_info:
        return ""
    subclass = item_info.get("subclass", "")
    # Only warn for armor slots where type matters (not trinkets, necks, etc.)
    armor_types = {"Cloth", "Leather", "Mail", "Plate"}
    if subclass in armor_types and subclass != "Mail":
        return f" [{subclass}]"
    return ""


def get_drop_chance(item_info: dict | None) -> float | None:
    """Extract drop chance from item info source data."""
    if not item_info:
        return None
    source = item_info.get("source")
    if isinstance(source, dict):
        return source.get("dropChance")
    if isinstance(source, list):
        for s in source:
            if "dropChance" in s:
                return s["dropChance"]
    return None


def format_drop_chance(item_info: dict | None) -> str:
    """Format drop chance for display, e.g. '~17% drop'."""
    chance = get_drop_chance(item_info)
    if chance is None:
        return ""
    # Some data sources store as 0-1 fraction, others as 0-100 percentage
    pct = chance if chance > 1 else chance * 100
    return f"~{pct:.0f}% drop"


def format_item_extras(item_info: dict | None) -> str:
    """Build parenthesized suffix with ilvl, quality, and drop chance."""
    ilvl = format_ilvl_quality(item_info)
    drop = format_drop_chance(item_info)
    parts = [p for p in (ilvl, drop) if p]
    return f"  ({', '.join(parts)})" if parts else ""


def format_rank_tag(upgrade: dict) -> str:
    """Format rank with Phase 0 only marker, e.g. 'BiS [Phase 0 only]'."""
    p0 = " [Phase 0 only]" if upgrade["phase0_only"] else ""
    return f"{upgrade['rank']}{p0}"


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


def classify_source(source: str) -> list[str]:
    """Return tags like 'dungeon', 'heroic', 'reputation', 'profession', etc."""
    s = source.lower()

    if "world drop" in s:
        return ["world_drop"]
    if "world boss" in s:
        return ["world_boss"]
    if "classic -" in s or "classic\u2014" in s:
        return ["classic_raid"]
    if "arena" in s or "pvp" in s or "gladiator" in s:
        return ["pvp"]
    if (
        "profession:" in s
        or "tailoring" in s
        or "leatherworking" in s
        or "blacksmithing" in s
    ):
        return ["profession"]

    tags = []
    for faction in FACTION_NAMES:
        if faction.lower() in s:
            tags.append("reputation")
            break
    if not tags and ("exalted" in s or "revered" in s or "honored" in s):
        tags.append("reputation")

    if "heroic" in s:
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
    if "badges of justice" in s or "badges" in s.split("(")[-1]:
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
    m = re.search(r"\((?:Heroic\s+)?(.+?)\)", source)
    if m:
        name = m.group(1)
        if name in dungeon_reputation:
            return name
    return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_character(path: str) -> dict:
    if path == "-":
        data = json.load(sys.stdin)
    else:
        p = Path(path)
        # If not found at given path, try data/ subdirectory
        if not p.exists():
            alt = PROJECT_ROOT / "data" / p.name
            if alt.exists():
                p = alt
        data = json.loads(p.read_text(encoding="utf-8"))
    return data if "character" not in data else data["character"]


def pretty_phase(phase_key: str) -> str:
    """Convert 'phase-1' to 'Phase 1' for display."""
    m = re.match(r"phase-(\d+)", phase_key)
    return f"Phase {m.group(1)}" if m else phase_key


# ---------------------------------------------------------------------------
# BiS slot resolution and ranking
# ---------------------------------------------------------------------------


def resolve_slot_key(bis_slot: str, phase_data: dict) -> str:
    """Handle slot name variance across phases (totems/idols, offhands/shields-offhands)."""
    if bis_slot == "totems" and bis_slot not in phase_data:
        return "idols"
    if bis_slot == "idols" and bis_slot not in phase_data:
        return "totems"
    if bis_slot == "offhands" and bis_slot not in phase_data:
        if "shields-offhands" in phase_data:
            return "shields-offhands"
    if bis_slot == "shields-offhands" and bis_slot not in phase_data:
        if "offhands" in phase_data:
            return "offhands"
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


def score_upgrade(rank: str, phase: str, current_phase: str) -> float:
    """
    Score an upgrade on a 100-point scale with phase decay.

    Base scores (current phase):
      BiS:    100  (1.0x multiplier)
      Option:  80  (0.8x multiplier)

    Each phase behind current halves the base score:
      1 phase behind: 0.5x  -> BiS=50, Option=40
      2 phases behind: 0.25x -> BiS=25, Option=20
      etc.
    """
    cur_num = int(current_phase.split("-")[1]) if "-" in current_phase else 0
    item_num = int(phase.split("-")[1]) if "-" in phase else 0

    phases_behind = max(0, cur_num - item_num)
    decay = 0.5**phases_behind

    base = 100 if rank == "BiS" else 80
    return base * decay


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
) -> list[dict]:
    """Find all dungeon/rep/badge upgrades for a single equipped slot."""
    slot_upgrades: list[dict] = []
    seen_item_ids: set[int] = set()

    for phase in phases_to_check:
        phase_data = bis_data["phases"].get(phase, {})
        slot_key = resolve_slot_key(bis_slot, phase_data)
        for bis_item in phase_data.get(slot_key, []):
            bis_id = bis_item.get("item_id")
            if bis_id == item_id or bis_id in seen_item_ids:
                continue
            if bis_id in all_equipped_ids:
                continue

            up_rank, up_phase, up_p0_only = get_effective_rank(
                bis_id, bis_slot, current_phase_data, phase0_data, current_phase
            )
            if not up_rank:
                continue

            source = bis_item.get("source", "")
            tags = classify_source(source)
            if (
                "dungeon" not in tags
                and "reputation" not in tags
                and "badges" not in tags
            ):
                continue

            seen_item_ids.add(bis_id)
            faction = extract_faction(source)
            rep_info = rep_lookup.get(faction) if faction else None
            dungeon = extract_dungeon(source, dungeon_reputation)
            item_score = score_upgrade(up_rank, up_phase, current_phase)
            required_standing = extract_required_standing(source)

            upgrade = {
                "name": sanitize_name(bis_item["name"]),
                "item_id": bis_id,
                "rank": up_rank,
                "phase": up_phase,
                "phase0_only": up_p0_only,
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

    # Promote normal dungeons to heroic if rep synergy exists
    for entry in list(dungeon_actions.values()):
        if not entry["heroic"]:
            heroic_key = f"Heroic {entry['dungeon']}"
            if heroic_key not in dungeon_actions:
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
            icon = (
                "D"
                if "dungeon" in up["tags"]
                else ("R" if "reputation" in up["tags"] else "B")
            )
            heroic = " (H)" if "heroic" in up["tags"] else ""
            rank_label = f"[{format_rank_tag(up)}]"
            armor = format_armor_warning(up.get("item_info"))
            extra = format_item_extras(up.get("item_info"))
            line = f"    [{icon}] {rank_label:18s} {up['name']}{armor}{extra}{heroic}  --  {up['source']}"
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


def print_no_upgrade(no_upgrade_slots: list[tuple[str, str, str, str]]):
    """Print slots with no dungeon/rep upgrade available."""
    if not no_upgrade_slots:
        return
    print("=== NO DUNGEON/REP UPGRADE (craft, raid, or world boss needed) ===")
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
    all_upgrades: list,
    no_upgrade_slots: list,
):
    """Print the summary section."""
    slot_count = len({up["slot"] for up in all_upgrades}) if all_upgrades else 0
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
    if slot_count:
        print(f"  Slots with dungeon/rep upgrades: {slot_count}")
    if no_upgrade_slots:
        print(f"  Slots needing raid/craft/other: {len(no_upgrade_slots)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_gear.py <character.json>")
        print("       echo '{...}' | python check_gear.py -")
        sys.exit(1)

    char = load_character(sys.argv[1])
    equipped = char.get("equippedItems", [])
    reputations_raw = char.get("reputations", [])

    # Flatten reputations
    rep_lookup: dict[str, dict] = {}
    for group in reputations_raw:
        for faction in group.get("factions", []):
            rep_lookup[faction["name"]] = faction

    # Build faction-aware dungeon rep mapping
    dungeon_reputation = build_dungeon_reputation(rep_lookup)

    # Load item database for enrichment
    item_db = load_item_db()

    # Load BiS data
    bis_data = json.loads(
        (PROJECT_ROOT / "output" / "bis_gear.json").read_text(encoding="utf-8")
    )
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
    )

    # Deduplicate ring/trinket upgrades for scoring
    scored_item_ids: set[int] = set()
    deduped_upgrades: list[dict] = []
    for up in all_upgrades:
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
    print_slot_breakdown(all_upgrades)
    print_no_upgrade(no_upgrade_slots)
    print_summary(
        cp,
        current_bis,
        current_option,
        old_bis,
        old_option,
        not_listed_slots,
        all_upgrades,
        no_upgrade_slots,
    )


if __name__ == "__main__":
    main()
