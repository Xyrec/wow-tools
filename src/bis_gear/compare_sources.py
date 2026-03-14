"""
Three-way comparison of BiS lists from Wowhead, Icy Veins, and AtlasLoot.

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


def load_item_db() -> dict[int, dict]:
    items_path = PROJECT_ROOT / "sources" / "item-data" / "items.json"
    if not items_path.exists():
        return {}
    items = json.loads(items_path.read_text(encoding="utf-8"))
    return {item["itemId"]: item for item in items}


def normalize_slot(slot: str) -> str:
    return SLOT_ALIASES.get(slot, slot)


def load_wowhead(phase: str) -> dict[str, dict[int, str]]:
    """Load wowhead BiS data. Returns {slot: {item_id: rank}}."""
    path = PROJECT_ROOT / "output" / "bis_gear.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    phase_data = data["phases"].get(phase, {})
    result: dict[str, dict[int, str]] = {}
    for slot, items in phase_data.items():
        canon = normalize_slot(slot)
        slot_dict = result.setdefault(canon, {})
        for item in items:
            iid = item.get("item_id")
            if iid:
                slot_dict[iid] = item.get("rank", "?")
    return result


def load_icy_veins(phase: str) -> dict[str, dict[int, str]]:
    """Load icy-veins BiS data. Returns {slot: {item_id: rank}}."""
    path = PROJECT_ROOT / "output" / "iv_bis_gear.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    phase_data = data["phases"].get(phase, {})
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


def main():
    phase = "phase-1"
    if "--phase" in sys.argv:
        idx = sys.argv.index("--phase")
        if idx + 1 < len(sys.argv):
            phase = sys.argv[idx + 1]

    item_db = load_item_db()

    wh = load_wowhead(phase)
    iv = load_icy_veins(phase)
    al = load_atlasloot()  # no phase dimension

    def name_for(item_id: int) -> str:
        info = item_db.get(item_id)
        return info["name"] if info else f"ID:{item_id}"

    def ilvl_for(item_id: int) -> int:
        info = item_db.get(item_id)
        return info.get("itemLevel", 0) if info else 0

    # Collect all items across all sources per slot
    print(f"=== THREE-WAY BIS COMPARISON ({phase.upper()}) ===")
    print("Sources: WH = Wowhead, IV = Icy Veins, AL = AtlasLoot")
    print("Ranks: B = BiS, O = Option, - = not listed")
    print()

    total_items = 0
    unanimous_bis = 0
    majority_bis = 0
    disagreements = 0

    for slot in SLOT_ORDER:
        wh_slot = wh.get(slot, {})
        iv_slot = iv.get(slot, {})
        al_slot = al.get(slot, {})

        # Collect all item IDs mentioned in any source
        all_ids = sorted(set(wh_slot) | set(iv_slot) | set(al_slot))
        if not all_ids:
            continue

        # Build rows
        rows: list[tuple[int, str, str, str, str, str, int]] = []
        for iid in all_ids:
            w = wh_slot.get(iid)
            i = iv_slot.get(iid)
            a = al_slot.get(iid)

            def short(rank: str | None) -> str:
                if rank is None:
                    return "-"
                if rank == "BiS":
                    return "B"
                if rank == "Option":
                    return "O"
                return rank[0].upper()

            ws, is_, as_ = short(w), short(i), short(a)

            # Determine vote
            bis_votes = sum(1 for r in (w, i, a) if r == "BiS")
            listed_votes = sum(1 for r in (w, i, a) if r is not None)

            if bis_votes == 3:
                vote = "UNANIMOUS BiS"
                unanimous_bis += 1
            elif bis_votes == 2:
                vote = "MAJORITY BiS"
                majority_bis += 1
            elif bis_votes == 1:
                vote = "1 says BiS"
                disagreements += 1
            elif listed_votes == 0:
                vote = ""
            else:
                vote = ""

            total_items += 1
            rows.append((iid, name_for(iid), ws, is_, as_, vote, ilvl_for(iid)))

        # Sort: unanimous BiS first, then majority, then by ilvl desc
        def sort_key(
            row: tuple[int, str, str, str, str, str, int],
        ) -> tuple[int, int]:
            vote = row[5]
            if "UNANIMOUS" in vote:
                tier = 0
            elif "MAJORITY" in vote:
                tier = 1
            elif "1 says" in vote:
                tier = 2
            else:
                tier = 3
            return (tier, -row[6])

        rows.sort(key=sort_key)

        print(f"--- {slot.upper()} ---")
        print(f"  {'Item':<42s} {'ilvl':>4s}  {'WH':>2s} {'IV':>2s} {'AL':>2s}  Vote")
        for iid, name, ws, is_, as_, vote, ilvl in rows:
            ilvl_str = str(ilvl) if ilvl else "?"
            print(
                f"  {name:<42s} {ilvl_str:>4s}   {ws:>1s}  {is_:>1s}  {as_:>1s}  {vote}"
            )
        print()

    # Summary
    print("=== SUMMARY ===")
    print(f"Total unique items across all sources: {total_items}")
    print(f"Unanimous BiS (all 3 agree): {unanimous_bis}")
    print(f"Majority BiS (2 of 3 agree): {majority_bis}")
    print(f"Contested BiS (only 1 says BiS): {disagreements}")


if __name__ == "__main__":
    main()
