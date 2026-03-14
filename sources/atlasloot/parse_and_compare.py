"""
Parse AtlasBIStooltips Shaman_Heal.lua and compare against our bis_gear.json.
Outputs a comparison showing matches, mismatches, and items unique to each list.
"""

import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent.parent

# The lua file has RECslot calls in slot order. Based on the WoW API slot IDs
# and the order they appear in the addon, the slots are:
# Head, Shoulder, Back, Chest, Wrist, Hands, Waist, Legs, Feet, Neck, Rings, Trinkets, Weapons, Offhands, Totems
# But we need to figure out the exact boundaries since the file is one long line.
# The rank resets to "1" at each new slot.

SLOT_NAMES = [
    "head", "shoulders", "back", "chest", "wrists", "hands",
    "waist", "legs", "feet", "neck", "rings", "trinkets",
    "weapons", "offhands", "totems"
]


def parse_lua_bis(filepath: Path) -> dict[str, list[dict]]:
    """Parse the RECslot calls from the lua file, splitting on rank=1 resets."""
    content = filepath.read_text(encoding="utf-8")

    # Extract all RECslot calls: sliccNote:RECslot(bis, "itemId", "rank")
    pattern = r'sliccNote:RECslot\(bis,\s*"(\d+)",\s*"(\d+)"\)'
    matches = re.findall(pattern, content)

    if not matches:
        print("No RECslot entries found!")
        return {}

    # Split into slots by detecting when rank resets to "1"
    slots_data: list[list[dict]] = []
    current_slot: list[dict] = []

    for item_id_str, rank_str in matches:
        rank = int(rank_str)
        if rank == 1 and current_slot:
            slots_data.append(current_slot)
            current_slot = []
        current_slot.append({"item_id": int(item_id_str), "rank": rank})

    if current_slot:
        slots_data.append(current_slot)

    print(f"Found {len(slots_data)} slots with {sum(len(s) for s in slots_data)} total items")

    # Map to slot names
    result = {}
    for i, slot_items in enumerate(slots_data):
        slot_name = SLOT_NAMES[i] if i < len(SLOT_NAMES) else f"unknown_{i}"
        result[slot_name] = slot_items

    return result


def load_our_bis() -> dict:
    """Load our bis_gear.json and return phase-0 and phase-1 data."""
    bis_path = PROJECT_DIR / "bis_gear.json"
    data = json.loads(bis_path.read_text(encoding="utf-8"))
    return data["phases"]


def compare(atlas_data: dict, our_phases: dict):
    """Compare AtlasLoot BiS items against our phase-0 and phase-1 lists."""

    # Build a lookup of all our item IDs per slot across phases
    our_items_by_slot: dict[str, dict[int, list[str]]] = {}
    for phase_name in ["phase-0", "phase-1"]:
        phase_data = our_phases.get(phase_name, {})
        for slot, items in phase_data.items():
            # Normalize slot names
            norm_slot = slot
            if slot in ("idols", "totems"):
                norm_slot = "totems"
            if slot == "shields-offhands":
                norm_slot = "offhands"

            if norm_slot not in our_items_by_slot:
                our_items_by_slot[norm_slot] = {}

            for item in items:
                iid = item.get("item_id")
                if iid:
                    if iid not in our_items_by_slot[norm_slot]:
                        our_items_by_slot[norm_slot][iid] = []
                    label = f"{phase_name} {item['rank']}"
                    if label not in our_items_by_slot[norm_slot][iid]:
                        our_items_by_slot[norm_slot][iid].append(label)

    # Also build reverse: our item names by ID
    our_names: dict[int, str] = {}
    for phase_data in our_phases.values():
        for items in phase_data.values():
            for item in items:
                if item.get("item_id"):
                    our_names[item["item_id"]] = item["name"]

    print("\n" + "=" * 80)
    print("COMPARISON: AtlasLoot BiS vs Our BiS Data (Phase 0 + Phase 1)")
    print("=" * 80)

    total_atlas = 0
    total_matched = 0
    total_atlas_only = 0
    total_ours_only = 0

    for slot_name in SLOT_NAMES:
        atlas_items = atlas_data.get(slot_name, [])
        our_slot = our_items_by_slot.get(slot_name, {})

        if not atlas_items and not our_slot:
            continue

        print(f"\n--- {slot_name.upper()} ---")

        atlas_ids = set()
        for item in atlas_items:
            total_atlas += 1
            iid = item["item_id"]
            atlas_ids.add(iid)
            atlas_rank = item["rank"]

            name = our_names.get(iid, f"(unknown item {iid})")
            if iid in our_slot:
                our_label = ", ".join(our_slot[iid])
                print(f"  MATCH    Atlas #{atlas_rank}  ID:{iid:5d}  {name:40s}  Ours: {our_label}")
                total_matched += 1
            else:
                print(f"  ATLAS    Atlas #{atlas_rank}  ID:{iid:5d}  {name:40s}  ** NOT in our data **")
                total_atlas_only += 1

        # Items in our data but not in AtlasLoot for this slot
        for iid, labels in our_slot.items():
            if iid not in atlas_ids:
                name = our_names.get(iid, f"(unknown item {iid})")
                label = ", ".join(labels)
                print(f"  OURS     ID:{iid:5d}  {name:40s}  {label}  ** NOT in AtlasLoot **")
                total_ours_only += 1

    print(f"\n{'=' * 80}")
    print(f"SUMMARY")
    print(f"  AtlasLoot total items: {total_atlas}")
    print(f"  Matched in both:       {total_matched}")
    print(f"  AtlasLoot only:        {total_atlas_only}")
    print(f"  Our data only:         {total_ours_only}")
    print(f"{'=' * 80}")


def main():
    lua_path = SCRIPT_DIR / "ClassDataBase" / "Shaman_Heal.lua"
    atlas_data = parse_lua_bis(lua_path)

    if not atlas_data:
        return

    # Print what we parsed
    print("\nParsed AtlasLoot slots:")
    for slot, items in atlas_data.items():
        ids = [str(i["item_id"]) for i in items]
        print(f"  {slot:12s}: {len(items)} items - IDs: {', '.join(ids)}")

    our_phases = load_our_bis()
    compare(atlas_data, our_phases)

    # Save parsed data for reference
    output_path = SCRIPT_DIR / "atlas_bis_parsed.json"
    output_path.write_text(json.dumps(atlas_data, indent=2), encoding="utf-8")
    print(f"\nParsed data saved to {output_path}")


if __name__ == "__main__":
    main()
