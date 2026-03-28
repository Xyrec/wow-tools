"""
Four-way comparison of BiS lists from AtlasLoot, WowTBC, Icy Veins, and WoWHead.

Shows agreement/disagreement across sources for each slot, with majority vote.

Usage:
    uv run bis-compare --spec resto
    uv run bis-compare --spec ele --phase phase-2
"""

import argparse
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
    "shields": "offhands",
    "idols": "totems",
    "librams": "totems",
}

SOURCE_LABELS = ["AL", "WT", "IV", "WH"]
SOURCE_NAMES = ["AtlasLoot", "wowtbc.gg", "Icy Veins", "WoWHead"]
SOURCE_FILES = [
    "al_bis_gear.json",
    "wtbc_bis_gear.json",
    "iv_bis_gear.json",
    "wh_bis_gear.json",
]

_SPEC_ALIASES = {
    "resto": "resto-shaman",
    "resto-shaman": "resto-shaman",
    "ele": "elemental-shaman",
    "elemental": "elemental-shaman",
    "elemental-shaman": "elemental-shaman",
    "prot": "prot-paladin",
    "protection": "prot-paladin",
    "prot-paladin": "prot-paladin",
}


def load_item_db() -> dict[int, dict]:
    items_path = PROJECT_ROOT / "sources" / "wowsims-tbc" / "items.json"
    if not items_path.exists():
        return {}
    items = json.loads(items_path.read_text(encoding="utf-8"))
    return {
        item["id"]: {"name": item["name"], "itemLevel": item.get("ilvl", 0)}
        for item in items
    }


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


def rank_short(rank: str | None) -> str:
    if rank is None:
        return "-"
    if rank == "BiS":
        return "B"
    if rank in ("Option", "Optional"):
        return "O"
    if rank == "Alternative":
        return "A"
    return rank[0].upper()


def vote_label(bis_count: int, total_sources: int) -> str:
    if bis_count == total_sources:
        return "UNANIMOUS BiS"
    if bis_count >= 3:
        return f"STRONG BiS ({bis_count}/{total_sources})"
    if bis_count == 2:
        return f"MAJORITY BiS ({bis_count}/{total_sources})"
    if bis_count == 1:
        return "1 says BiS"
    return ""


def main():
    parser = argparse.ArgumentParser(description="Compare BiS lists across 4 sources")
    parser.add_argument("--spec", required=True, help="Spec: resto, ele, prot")
    parser.add_argument(
        "--phase", default=None, help="Phase to compare (default: current-phase.txt)"
    )
    args = parser.parse_args()

    key = args.spec.strip().lower()
    if key not in _SPEC_ALIASES:
        print(f"Unknown spec '{args.spec}'. Use: resto, ele, prot.")
        sys.exit(1)
    spec = _SPEC_ALIASES[key]

    phase = args.phase
    if not phase:
        phase_file = PROJECT_ROOT / "data" / "current-phase.txt"
        phase = (
            phase_file.read_text(encoding="utf-8").strip()
            if phase_file.exists()
            else "phase-1"
        )

    item_db = load_item_db()

    # Load all 4 sources
    output_dir = PROJECT_ROOT / "output" / spec
    sources = [
        load_phase_source(output_dir / src_file, phase) for src_file in SOURCE_FILES
    ]
    loaded = sum(1 for i, f in enumerate(SOURCE_FILES) if (output_dir / f).exists())

    def name_for(item_id: int) -> str:
        info = item_db.get(item_id)
        return info["name"] if info else f"ID:{item_id}"

    def ilvl_for(item_id: int) -> int:
        info = item_db.get(item_id)
        return info.get("itemLevel", 0) if info else 0

    label_header = " ".join(f"{lbl:>2s}" for lbl in SOURCE_LABELS)

    print(f"=== FOUR-WAY BIS COMPARISON ({phase.upper()}) — {spec} ===")
    print(
        "Sources: "
        + ", ".join(f"{lbl} = {name}" for lbl, name in zip(SOURCE_LABELS, SOURCE_NAMES))
    )
    print(f"Loaded: {loaded}/{len(SOURCE_FILES)} source files")
    print("Ranks: B = BiS, O = Optional, A = Alternative, - = not listed")
    print()

    total_items = 0
    unanimous_bis = 0
    strong_bis = 0
    majority_bis = 0
    contested_bis = 0

    for slot in SLOT_ORDER:
        slot_data = [s.get(slot, {}) for s in sources]

        all_ids: set[int] = set()
        for sd in slot_data:
            all_ids.update(sd.keys())
        if not all_ids:
            continue

        rows: list[tuple[int, str, list[str], str, int]] = []
        for iid in sorted(all_ids):
            ranks = [sd.get(iid) for sd in slot_data]
            shorts = [rank_short(r) for r in ranks]

            bis_count = sum(1 for r in ranks if r == "BiS")
            label = vote_label(bis_count, loaded)

            if bis_count == loaded:
                unanimous_bis += 1
            elif bis_count >= 3:
                strong_bis += 1
            elif bis_count == 2:
                majority_bis += 1
            elif bis_count == 1:
                contested_bis += 1

            total_items += 1
            rows.append((iid, name_for(iid), shorts, label, ilvl_for(iid)))

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
        for _iid, name, shorts, label, ilvl in rows:
            ilvl_str = str(ilvl) if ilvl else "?"
            rank_cols = "  ".join(f"{s:>1s}" for s in shorts)
            print(f"  {name:<42s} {ilvl_str:>4s}   {rank_cols}  {label}")
        print()

    print("=== SUMMARY ===")
    print(f"Total unique items across all sources: {total_items}")
    print(f"Unanimous BiS (all {loaded} agree): {unanimous_bis}")
    if strong_bis:
        print(f"Strong BiS (3/{loaded} agree): {strong_bis}")
    print(f"Majority BiS (2/{loaded} agree): {majority_bis}")
    print(f"Contested BiS (only 1 says BiS): {contested_bis}")


if __name__ == "__main__":
    main()
