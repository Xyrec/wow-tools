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

HORDE_RACES = {"Orc", "Troll", "Tauren", "Undead", "Blood Elf"}
ALLIANCE_RACES = {"Human", "Dwarf", "Night Elf", "Gnome", "Draenei"}


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
        raid_keywords = [
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
        if not any(rk in s for rk in raid_keywords):
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
    for faction in FACTION_NAMES:
        if faction.lower() in source.lower():
            return faction
    return None


def extract_dungeon(source: str, dungeon_reputation: dict) -> str | None:
    m = re.search(r"\((?:Heroic\s+)?(.+?)\)", source)
    if m:
        name = m.group(1)
        if name in dungeon_reputation:
            return name
    return None


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

    Examples for current_phase = phase-2:
      Phase 2 BiS: 100, Phase 2 Option: 80
      Phase 1 BiS:  50, Phase 1 Option: 40
      Phase 0 BiS:  25, Phase 0 Option: 20
    """
    # Extract phase numbers
    cur_num = int(current_phase.split("-")[1]) if "-" in current_phase else 0
    item_num = int(phase.split("-")[1]) if "-" in phase else 0

    phases_behind = max(0, cur_num - item_num)
    decay = 0.5**phases_behind

    base = 100 if rank == "BiS" else 80
    return base * decay


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_gear.py <character.json>")
        print("       echo '{...}' | python check_gear.py -")
        sys.exit(1)

    char = load_character(sys.argv[1])
    equipped = char.get("equippedItems", [])
    reputations_raw = char.get("reputations", [])

    # Flatten reputations
    rep_lookup = {}
    for group in reputations_raw:
        for faction in group.get("factions", []):
            rep_lookup[faction["name"]] = faction

    # Build faction-aware dungeon rep mapping
    dungeon_reputation = build_dungeon_reputation(rep_lookup)

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

    # Collect all equipped item IDs so we can skip recommending items already worn
    all_equipped_ids = {item["itemId"] for item in equipped}

    # Categorize each equipped item into tiers
    current_bis = []
    current_option = []
    old_bis = []
    old_option = []
    not_listed_slots = []
    all_upgrades = []
    no_upgrade_slots = []

    for bis_slot, items in equipped_by_slot.items():
        for eq_item in items:
            item_id = eq_item["itemId"]
            item_name = eq_item["itemName"]
            slot_label = eq_item["slotName"]

            # Determine equipped item's rank with phase priority
            eq_rank, eq_phase, eq_p0_only = get_effective_rank(
                item_id, bis_slot, current_phase_data, phase0_data, current_phase
            )

            # Classify into tier
            if eq_rank == "BiS" and not eq_p0_only:
                current_bis.append((slot_label, item_name))
                continue
            elif eq_rank == "Option" and not eq_p0_only:
                current_option.append((slot_label, item_name))
            elif eq_rank == "BiS" and eq_p0_only:
                old_bis.append((slot_label, item_name))
            elif eq_rank == "Option" and eq_p0_only:
                old_option.append((slot_label, item_name))
            elif eq_rank == "PvP":
                if eq_p0_only:
                    old_option.append((slot_label, item_name))
                else:
                    current_option.append((slot_label, item_name))
            else:
                not_listed_slots.append((slot_label, item_name))

            # Find upgrades from dungeons/reps/badges for this slot
            slot_upgrades = []
            seen_item_ids = set()

            for phase in phases_to_check:
                phase_data = bis_data["phases"].get(phase, {})
                slot_key = resolve_slot_key(bis_slot, phase_data)
                for bis_item in phase_data.get(slot_key, []):
                    bis_id = bis_item.get("item_id")
                    if bis_id == item_id or bis_id in seen_item_ids:
                        continue
                    # Skip items already equipped in another slot (e.g. ring in other finger)
                    if bis_id in all_equipped_ids:
                        continue

                    up_rank, up_phase, up_p0_only = get_effective_rank(
                        bis_id, bis_slot, current_phase_data, phase0_data, current_phase
                    )
                    if not up_rank:
                        continue

                    source = bis_item.get("source", "")
                    tags = classify_source(source)
                    # Include dungeon drops, rep vendors, and badge vendors
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
                    }
                    slot_upgrades.append(upgrade)
                    all_upgrades.append(upgrade)

            if not slot_upgrades:
                no_upgrade_slots.append(
                    (slot_label, item_name, eq_rank or "Not on list")
                )

    # --- Deduplicate ring/trinket upgrades in scoring ---
    # For shared slots (rings, trinkets), the same upgrade item_id may appear
    # for both slots. Only count it once in dungeon scoring.
    scored_item_ids: set[int] = set()
    deduped_upgrades_for_scoring: list[dict] = []
    for up in all_upgrades:
        if up["item_id"] not in scored_item_ids:
            scored_item_ids.add(up["item_id"])
            deduped_upgrades_for_scoring.append(up)

    # --- Collect reputation needs (deduplicated) ---
    rep_needs: dict[str, list[dict]] = defaultdict(list)
    rep_needs_seen: dict[str, set] = defaultdict(set)
    for up in deduped_upgrades_for_scoring:
        if "reputation" in up["tags"] and up["faction"]:
            if up["item_id"] not in rep_needs_seen[up["faction"]]:
                rep_needs_seen[up["faction"]].add(up["item_id"])
                rep_needs[up["faction"]].append(up)

    # --- Build dungeon priority list (using deduplicated scores) ---
    dungeon_actions: dict[str, dict] = {}
    for up in deduped_upgrades_for_scoring:
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
        p0 = " (Phase 0 only)" if up["phase0_only"] else ""
        entry["score_breakdown"].append(f"{up['rank']}{p0} drop: +{up['score']:.0f}")

    # Add rep synergy scoring
    for key, entry in dungeon_actions.items():
        faction = entry["rep_faction"]
        if faction and faction in rep_needs:
            entry["rep_vendor_items"] = rep_needs[faction]
            rep_score = sum(vi["score"] for vi in rep_needs[faction])
            entry["score"] += rep_score
            entry["score_breakdown"].append(
                f"rep toward {faction} vendor items: +{rep_score:.0f}"
            )
        if entry["badges"]:
            # Badge bonus = 10% of total badge vendor item value (meaningful but not dominant)
            badge_items = [
                u for u in deduped_upgrades_for_scoring if "badges" in u["tags"]
            ]
            if badge_items:
                badge_bonus = round(sum(b["score"] for b in badge_items) * 0.1)
                if badge_bonus > 0:
                    entry["score"] += badge_bonus
                    entry["score_breakdown"].append(
                        f"badges toward vendor items: +{badge_bonus}"
                    )

    # Promote normal dungeons to heroic if rep synergy exists
    for key, entry in list(dungeon_actions.items()):
        if not entry["heroic"]:
            heroic_key = f"Heroic {entry['dungeon']}"
            if heroic_key not in dungeon_actions:
                faction = entry["rep_faction"]
                if faction and faction in rep_needs:
                    badge_items = [
                        u for u in deduped_upgrades_for_scoring if "badges" in u["tags"]
                    ]
                    badge_bonus = (
                        round(sum(b["score"] for b in badge_items) * 0.1)
                        if badge_items
                        else 0
                    )
                    heroic_entry = {
                        "key": heroic_key,
                        "dungeon": entry["dungeon"],
                        "heroic": True,
                        "drops": list(entry["drops"]),  # copy to avoid aliasing
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

    # Reputation-only actions
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

    sorted_dungeons = sorted(
        dungeon_actions.values(), key=lambda x: x["score"], reverse=True
    )
    sorted_rep = sorted(rep_actions, key=lambda x: x["score"], reverse=True)

    # --- Output ---
    cp = pretty_phase(current_phase)
    print(
        f"Character: {char.get('name', '?')} ({char.get('class', '?')}) "
        f"-- Checking against: {', '.join(pretty_phase(p) for p in phases_to_check)}"
    )
    print(f"   Current phase: {cp} (authoritative) | Phase 0 (fallback)\n")

    # Current phase BiS
    if current_bis:
        print(f"=== {cp.upper()} BIS (you're set) ===")
        for slot, name in current_bis:
            print(f"  {slot:12s}  {name}")
        print()

    # Current phase Option
    if current_option:
        print(f"=== {cp.upper()} OPTION (upgrade available this phase) ===")
        for slot, name in current_option:
            print(f"  {slot:12s}  {name}")
        print()

    # Phase 0 only items (outdated)
    if old_bis or old_option:
        print(f"=== PHASE 0 ONLY (not in {cp} list -- outdated) ===")
        for slot, name in old_bis:
            print(f"  {slot:12s}  {name}  [was Phase 0 BiS]")
        for slot, name in old_option:
            print(f"  {slot:12s}  {name}  [was Phase 0 Option]")
        print()

    # Not on any list
    if not_listed_slots:
        print("=== NOT ON ANY BIS LIST ===")
        for slot, name in not_listed_slots:
            print(f"  {slot:12s}  {name}")
        print()

    # Priority dungeons
    if sorted_dungeons:
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
            # Score breakdown
            print(f"       Score: {' | '.join(entry['score_breakdown'])}")

            for drop in entry["drops"]:
                p0_tag = " [Phase 0 only]" if drop["phase0_only"] else ""
                rank_tag = f"{drop['rank']}{p0_tag}"
                print(
                    f"       [{rank_tag:16s}]  {drop['name']}  ({drop['slot']} -- replaces {drop['current_item']})"
                )

            if entry["rep_vendor_items"]:
                print("       Also earns rep toward:")
                for vi in entry["rep_vendor_items"]:
                    p0_tag = " [Phase 0 only]" if vi["phase0_only"] else ""
                    rank_tag = f"{vi['rank']}{p0_tag}"
                    print(f"         [{rank_tag:16s}]  {vi['name']}  ({vi['slot']})")
        print()

    # Reputation goals
    if sorted_rep:
        print("=== REPUTATION GOALS ===")
        for entry in sorted_rep:
            ri = entry["rep_info"]
            print(
                f"\n  {entry['faction']}  (You: {ri['standing']}, {ri['remainingRep']:,} rep to next tier)"
            )
            for item in entry["items"]:
                p0_tag = " [Phase 0 only]" if item["phase0_only"] else ""
                rank_tag = f"{item['rank']}{p0_tag}"
                # Show total rep to required standing
                req = item.get("required_standing")
                rep_detail = ""
                if req and ri:
                    total = calc_rep_to_standing(
                        ri["standing"], ri["remainingRep"], req
                    )
                    if total is not None and total > 0:
                        rep_detail = f"  -- need {req}, ~{total:,} rep to go"
                    elif total == 0:
                        rep_detail = f"  -- need {req}, READY TO BUY"
                print(
                    f"    [{rank_tag:16s}]  {item['name']}  ({item['slot']} -- replaces {item['current_item']}){rep_detail}"
                )
            if entry["dungeons_for_rep"]:
                print(f"    Grind via: {', '.join(entry['dungeons_for_rep'])}")
        print()

    # Per-slot breakdown
    slot_groups: dict[str, list[dict]] = defaultdict(list)
    for up in all_upgrades:
        slot_groups[up["slot"]].append(up)

    if slot_groups:
        print("=== ALL UPGRADES BY SLOT ===")
        for slot in dict.fromkeys(up["slot"] for up in all_upgrades):
            items_in_slot = slot_groups[slot]
            current = items_in_slot[0]["current_item"]
            current_rank = items_in_slot[0]["current_rank"]
            rank_note = f" [{current_rank}]" if current_rank != "Not on list" else ""
            print(f"\n  {slot}: {current}{rank_note}")
            for up in items_in_slot:
                icon = (
                    "D"
                    if "dungeon" in up["tags"]
                    else ("R" if "reputation" in up["tags"] else "B")
                )
                heroic = " (H)" if "heroic" in up["tags"] else ""
                p0_tag = " [Phase 0 only]" if up["phase0_only"] else ""
                rank_label = f"[{up['rank']}{p0_tag}]"
                line = f"    [{icon}] {rank_label:18s} {up['name']}{heroic}  --  {up['source']}"
                if up["rep_info"]:
                    ri = up["rep_info"]
                    req = up.get("required_standing")
                    if req:
                        total = calc_rep_to_standing(
                            ri["standing"], ri["remainingRep"], req
                        )
                        if total is not None and total > 0:
                            line += f"  (need {req}, ~{total:,} rep)"
                        elif total == 0:
                            line += "  (READY TO BUY)"
                    else:
                        line += f"  (You: {ri['standing']} -- {ri['remainingRep']:,} rep to next tier)"
                print(line)
        print()

    # No dungeon/rep upgrade
    if no_upgrade_slots:
        print("=== NO DUNGEON/REP UPGRADE (craft, raid, or world boss needed) ===")
        for slot, name, rank in no_upgrade_slots:
            print(f"  {slot:12s}  {name} [{rank}]")
        print()

    # Summary
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
    if slot_groups:
        print(f"  Slots with dungeon/rep upgrades: {len(slot_groups)}")
    if no_upgrade_slots:
        print(f"  Slots needing raid/craft/other: {len(no_upgrade_slots)}")


if __name__ == "__main__":
    main()
