"""
Four-way comparison of BiS lists from Wowhead, Icy Veins, AtlasLoot, and wowtbc.gg.

Shows agreement/disagreement across sources for each slot, with majority vote.

Usage:
    uv run bis-compare
    uv run bis-compare --phase phase-2
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Canonical slot order for display
SLOT_ORDER = [
    "head",
    "neck",
    "shoulders",
    "back",
    "chest",
    "wrists",
    "hands",
    "waist",
    "legs",
    "feet",
    "rings",
    "trinkets",
    "weapons",
    "offhands",
    "totems",
]

# Map variant slot keys to canonical
SLOT_ALIASES = {
    "shields-offhands": "offhands",
    "idols": "totems",
}

SOURCE_LABELS = ["WH", "IV", "AL", "WT"]
SOURCE_NAMES = ["Wowhead", "Icy Veins", "AtlasLoot", "wowtbc.gg"]


def load_item_db() -> dict[int, dict]:
    items_path = PROJECT_ROOT / "sources" / "item-data" / "items.json"
    if not items_path.exists():
        return {}
    items = json.loads(items_path.read_text(encoding="utf-8"))
    return {item["itemId"]: item for item in items}


def normalize_slot(slot: str) -> str:
    return SLOT_ALIASES.get(slot, slot)


def load_phase_source(path: Path, phase: str) -> dict[str, dict[int, str]]:
    """Load a phase-based BiS JSON file. Returns {slot: {item_id: rank}}."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    phase_data = data.get("phases", {}).get(phase, {})
    result: dict[str, dict[int, str]] = {}
    for slot, items in phase_data.items():
        canon = normalize_slot(slot)
        slot_dict = result.setdefault(canon, {})
        for item in items:
            iid = item.get("item_id")
            if iid:
                slot_dict[iid] = item.get("rank", "?")
    return result


def load_atlasloot() -> dict[str, dict[int, str]]:
    """Load AtlasLoot BiS data. Returns {slot: {item_id: rank}}.
    Rank 1 -> 'BiS', rank > 1 -> 'Option'."""
    path = PROJECT_ROOT / "sources" / "atlasloot" / "atlas_bis_parsed.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[int, str]] = {}
    for slot, items in data.items():
        canon = normalize_slot(slot)
        slot_dict = result.setdefault(canon, {})
        for item in items:
            iid = item.get("item_id")
            rank_num = item.get("rank", 99)
            if iid:
                slot_dict[iid] = "BiS" if rank_num == 1 else "Option"
    return result


def rank_short(rank: str | None) -> str:
    if rank is None:
        return "-"
    if rank == "BiS":
        return "B"
    if rank == "Option":
        return "O"
    return rank[0].upper()


def vote_label(bis_count: int, total_sources: int) -> str:
    if bis_count == total_sources:
        return "UNANIMOUS BiS"
    if bis_count >= 3:
        return "STRONG BiS"
    if bis_count == 2:
        return "MAJORITY BiS"
    if bis_count == 1:
        return "1 says BiS"
    return ""


def main():
    phase = "phase-1"
    if "--phase" in sys.argv:
        idx = sys.argv.index("--phase")
        if idx + 1 < len(sys.argv):
            phase = sys.argv[idx + 1]

    item_db = load_item_db()

    # Load all 4 sources
    sources = [
        load_phase_source(PROJECT_ROOT / "output" / "bis_gear.json", phase),
        load_phase_source(PROJECT_ROOT / "output" / "iv_bis_gear.json", phase),
        load_atlasloot(),  # no phase dimension
        load_phase_source(PROJECT_ROOT / "output" / "wtbc_bis_gear.json", phase),
    ]

    def name_for(item_id: int) -> str:
        info = item_db.get(item_id)
        return info["name"] if info else f"ID:{item_id}"

    def ilvl_for(item_id: int) -> int:
        info = item_db.get(item_id)
        return info.get("itemLevel", 0) if info else 0

    num_sources = len(sources)
    label_header = " ".join(f"{lbl:>2s}" for lbl in SOURCE_LABELS)

    print(f"=== FOUR-WAY BIS COMPARISON ({phase.upper()}) ===")
    print(
        "Sources: "
        + ", ".join(f"{lbl} = {name}" for lbl, name in zip(SOURCE_LABELS, SOURCE_NAMES))
    )
    print("Ranks: B = BiS, O = Option, - = not listed")
    print()

    total_items = 0
    unanimous_bis = 0
    strong_bis = 0
    majority_bis = 0
    contested_bis = 0

    for slot in SLOT_ORDER:
        slot_data = [s.get(slot, {}) for s in sources]

        # Collect all item IDs mentioned in any source
        all_ids: set[int] = set()
        for sd in slot_data:
            all_ids.update(sd.keys())
        if not all_ids:
            continue

        # Build rows
        rows: list[tuple[int, str, list[str], str, int]] = []
        for iid in sorted(all_ids):
            ranks = [sd.get(iid) for sd in slot_data]
            shorts = [rank_short(r) for r in ranks]

            bis_count = sum(1 for r in ranks if r == "BiS")
            label = vote_label(bis_count, num_sources)

            if bis_count == num_sources:
                unanimous_bis += 1
            elif bis_count >= 3:
                strong_bis += 1
            elif bis_count == 2:
                majority_bis += 1
            elif bis_count == 1:
                contested_bis += 1

            total_items += 1
            rows.append((iid, name_for(iid), shorts, label, ilvl_for(iid)))

        # Sort: unanimous first, then strong, majority, contested, then by ilvl desc
        def sort_key(
            row: tuple[int, str, list[str], str, int],
        ) -> tuple[int, int]:
            label = row[3]
            if "UNANIMOUS" in label:
                tier = 0
            elif "STRONG" in label:
                tier = 1
            elif "MAJORITY" in label:
                tier = 2
            elif "1 says" in label:
                tier = 3
            else:
                tier = 4
            return (tier, -row[4])

        rows.sort(key=sort_key)

        print(f"--- {slot.upper()} ---")
        print(f"  {'Item':<42s} {'ilvl':>4s}  {label_header}  Vote")
        for iid, name, shorts, label, ilvl in rows:
            ilvl_str = str(ilvl) if ilvl else "?"
            rank_cols = "  ".join(f"{s:>1s}" for s in shorts)
            print(f"  {name:<42s} {ilvl_str:>4s}   {rank_cols}  {label}")
        print()

    # Summary
    print("=== SUMMARY ===")
    print(f"Total unique items across all sources: {total_items}")
    print(f"Unanimous BiS (all 4 agree): {unanimous_bis}")
    print(f"Strong BiS (3 of 4 agree): {strong_bis}")
    print(f"Majority BiS (2 of 4 agree): {majority_bis}")
    print(f"Contested BiS (only 1 says BiS): {contested_bis}")


if __name__ == "__main__":
    main()
