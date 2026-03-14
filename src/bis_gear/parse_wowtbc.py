"""
Parses wowtbc.gg TBC Resto Shaman BiS HTML files into a structured JSON file.

The wowtbc pages list items per slot in ranked order. The first item in each slot
(with item__arrow) is BiS; subsequent items (with item__value) are Options.
Items are identified by name only (no item IDs in the HTML), so we resolve IDs
from the item database.

Usage:
    uv run wtbc-parse
    uv run wtbc-parse --output custom_output.json
"""

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Map wowtbc slot IDs to our canonical slot keys
SLOT_NAME_MAP = {
    "head": "head",
    "neck": "neck",
    "shoulder": "shoulders",
    "back": "back",
    "chest": "chest",
    "wrist": "wrists",
    "hands": "hands",
    "waist": "waist",
    "legs": "legs",
    "feet": "feet",
    "finger_1": "rings",
    "finger_2": "rings",
    "trinket_1": "trinkets",
    "trinket_2": "trinkets",
    "weapon": "weapons",
    "off_hand": "offhands",
    "relic": "totems",
}


class WowtbcParser(HTMLParser):
    """Parses wowtbc.gg BiS HTML files extracting gear items per slot."""

    def __init__(self, name_to_id: dict[str, int]):
        super().__init__()
        self.results: dict[str, list[dict[str, str | int]]] = {}
        self._name_to_id = name_to_id

        # Slot tracking
        self._current_slot: str | None = None
        self._slot_item_count = 0

        # Item tracking
        self._in_item = False
        self._in_item_name = False
        self._item_name = ""
        self._in_instance = False
        self._instance_text = ""
        self._in_boss = False
        self._boss_text = ""

    def _flush_pending_item(self):
        """Flush the current pending item if one exists."""
        if self._in_item and self._item_name.strip() and self._current_slot:
            self._add_item()
        self._in_item = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr: dict[str, str] = {k: v or "" for k, v in attrs}
        css = attr.get("class", "")

        if tag == "div" and "bis__card" in css and "bis__card--expanded" in css:
            # New slot card — flush any pending item from previous slot
            self._flush_pending_item()
            slot_id = attr.get("id", "")
            self._current_slot = SLOT_NAME_MAP.get(slot_id)
            self._slot_item_count = 0
        elif tag == "div" and "item" in css.split() and self._current_slot:
            # New item div — flush previous item if it had no boss div
            self._flush_pending_item()
            self._in_item = True
            self._item_name = ""
            self._instance_text = ""
            self._boss_text = ""
        elif tag == "div" and "item__name" in css and "item__name__wrapper" not in css:
            self._in_item_name = True
            self._item_name = ""
        elif tag == "div" and "item__instance" in css:
            self._in_instance = True
            self._instance_text = ""
        elif tag == "div" and "item__boss" in css:
            self._in_boss = True
            self._boss_text = ""

    def handle_endtag(self, tag: str):
        if tag == "div" and self._in_item_name:
            self._in_item_name = False
        elif tag == "div" and self._in_instance:
            self._in_instance = False
        elif tag == "div" and self._in_boss:
            self._in_boss = False

    def handle_data(self, data: str):
        if self._in_item_name:
            self._item_name += data
        if self._in_instance:
            self._instance_text += data
        if self._in_boss:
            self._boss_text += data

    def _add_item(self):
        if not self._current_slot:
            return

        name = self._item_name.strip()
        if not name:
            return

        self._slot_item_count += 1
        rank = "BiS" if self._slot_item_count == 1 else "Option"

        source_parts = []
        instance = self._instance_text.strip()
        boss = self._boss_text.strip()
        if instance:
            source_parts.append(instance)
        if boss:
            source_parts.append(boss)
        source = " — ".join(source_parts)

        item: dict[str, str | int] = {
            "rank": rank,
            "name": name,
            "source": source,
        }

        # Resolve item ID from name (try exact match, then case-insensitive)
        item_id = self._name_to_id.get(name)
        if not item_id:
            item_id = self._name_to_id.get(name.lower())
        if item_id:
            item["item_id"] = item_id

        self.results.setdefault(self._current_slot, []).append(item)

    def close(self):
        """Flush any remaining pending item at end of document."""
        self._flush_pending_item()
        super().close()


def build_name_to_id() -> dict[str, int]:
    """Build a name-to-item-ID mapping from items.json.

    Stores exact-case keys and lowercase keys separately for fallback.
    """
    items_path = PROJECT_ROOT / "sources" / "item-data" / "items.json"
    if not items_path.exists():
        return {}
    items = json.loads(items_path.read_text(encoding="utf-8"))
    exact: dict[str, int] = {}
    lower: dict[str, int] = {}
    for item in items:
        name = item.get("name", "")
        if name:
            if name not in exact:
                exact[name] = item["itemId"]
            low = name.lower()
            if low not in lower:
                lower[low] = item["itemId"]
    # Merge: exact keys take priority over lowercase keys
    lower.update(exact)
    return lower


def parse_phase_file(
    filepath: Path, name_to_id: dict[str, int]
) -> dict[str, list[dict[str, str | int]]]:
    parser = WowtbcParser(name_to_id)
    parser.feed(filepath.read_text(encoding="utf-8"))
    parser.close()
    return parser.results


def main():
    output_path = PROJECT_ROOT / "output" / "wtbc_bis_gear.json"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = Path(sys.argv[idx + 1])

    # Read current phase
    current_phase_file = PROJECT_ROOT / "data" / "current-phase.txt"
    current_phase = (
        current_phase_file.read_text(encoding="utf-8").strip()
        if current_phase_file.exists()
        else None
    )

    # Build name-to-ID mapping
    name_to_id = build_name_to_id()

    # Parse all phase files
    result: dict[str, str | dict] = {}
    if current_phase:
        result["current_phase"] = current_phase
    phase_files = sorted((PROJECT_ROOT / "sources" / "wowtbc").glob("phase-*.html"))
    if not phase_files:
        print("No phase-*.html files found in sources/wowtbc/.")
        sys.exit(1)

    phases: dict[str, dict] = {}
    for pf in phase_files:
        phase_name = pf.stem
        print(f"Parsing {pf.name}...")
        slots = parse_phase_file(pf, name_to_id)
        phases[phase_name] = slots

    result["phases"] = phases

    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWrote {output_path} with {len(phases)} phases.")
    for phase, slots in phases.items():
        total_items = sum(len(items) for items in slots.values())
        resolved = sum(1 for items in slots.values() for i in items if "item_id" in i)
        print(
            f"  {phase}: {len(slots)} slots, {total_items} items ({resolved} with IDs)"
        )


if __name__ == "__main__":
    main()
