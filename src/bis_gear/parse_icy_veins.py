"""
Parses Icy Veins TBC BiS HTML files into a structured JSON file.

The icy-veins pages have one or two tables per phase:
  1. "Best in Slot Table" — items here are ranked as "BiS"
  2. "Other Useful ... Gear" — items here are ranked as "Option" (optional)

Slot names may appear in <td><strong>SlotName</strong></td> (shaman pages) or
plain <td>SlotName</td> (paladin pages). Items may be in <li> tags or directly
in the item <td> cell without list wrappers.

Usage:
    uv run iv-parse --spec resto
    uv run iv-parse --spec ele
    uv run iv-parse --spec prot
    uv run iv-parse --spec resto --output custom_output.json

Spec aliases: resto, resto-shaman | ele, elemental, elemental-shaman | prot, prot-paladin
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

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


def resolve_spec(raw: str) -> str:
    key = raw.strip().lower()
    if key not in _SPEC_ALIASES:
        print(f"Unknown spec '{raw}'. Use: resto, ele, prot.")
        sys.exit(1)
    return _SPEC_ALIASES[key]


# Map icy-veins slot names to our canonical slot keys.
# Elemental pages use slightly different names for some slots (shoulder, cloak, gloves, relics).
SLOT_NAME_MAP = {
    "helm": "head",
    "neck": "neck",
    "shoulders": "shoulders",
    "shoulder": "shoulders",  # elemental / prot-paladin phases 1-5
    "back": "back",
    "cloak": "back",  # elemental / prot-paladin phases 1-5
    "chest": "chest",
    "wrists": "wrists",
    "bracer": "wrists",  # prot-paladin phases 1-5
    "bracers": "wrists",  # prot-paladin
    "hands": "hands",
    "gloves": "hands",  # elemental / prot-paladin phases 1-5
    "belt": "waist",
    "waist": "waist",  # prot-paladin phase-0
    "legs": "legs",
    "boots": "feet",
    "feet": "feet",  # prot-paladin phase-0
    "rings": "rings",
    "ring 1": "rings",  # prot-paladin phases 1-5 (individual ring slots)
    "ring 2": "rings",  # prot-paladin phases 1-5
    "trinkets": "trinkets",
    "trinket 1": "trinkets",  # prot-paladin phases 1-5 (individual trinket slots)
    "trinket 2": "trinkets",  # prot-paladin phases 1-5
    "two-hand": "weapons",
    "one-hand": "weapons",
    "weapon": "weapons",  # prot-paladin phases 1-5
    "weapons": "weapons",  # prot-paladin phase-0
    "off-hand": "offhands",
    "shield": "shields-offhands",  # prot paladin
    "shields": "shields-offhands",  # prot paladin
    "relic": "totems",
    "relics": "totems",  # elemental
    "libram": "totems",  # prot paladin (same canonical slot)
    "librams": "totems",  # prot paladin
}


class IcyVeinsParser(HTMLParser):
    """Parses icy-veins BiS HTML files extracting gear slot tables."""

    def __init__(self):
        super().__init__()
        self.results: dict[str, list[dict[str, str | int]]] = {}

        # Table tracking
        self._in_bis_table = False
        self._in_alt_table = False
        self._table_count = 0
        self._bis_table_idx: int | None = None
        self._alt_table_idx: int | None = None

        # Heading detection (h2/h3 signal BiS table; h2/h4 signal alt table)
        self._in_h2 = False
        self._in_h3 = False
        self._in_h4 = False
        self._heading_text = ""

        # Row/cell tracking
        self._in_row = False
        self._in_cell = False
        self._cell_idx = -1
        self._cell_text = ""
        self._is_slot_cell = False
        self._in_strong = False
        self._strong_text = ""
        self._has_strong = False

        # Current slot
        self._current_slot: str | None = None

        # Item tracking (per <li>)
        self._in_li = False
        self._current_item_id: int | None = None
        self._current_item_name = ""
        self._current_rank = "BiS"  # default, overridden by table type

        # Source text collection (everything after item span in <li>)
        self._source_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr: dict[str, str] = {k: v or "" for k, v in attrs}

        if tag == "h2":
            self._in_h2 = True
            self._heading_text = ""
        elif tag == "h3":
            self._in_h3 = True
            self._heading_text = ""
        elif tag == "h4":
            self._in_h4 = True
            self._heading_text = ""
        elif tag == "table":
            self._table_count += 1
            if self._bis_table_idx == self._table_count:
                self._in_bis_table = True
                self._current_rank = "BiS"
            elif self._alt_table_idx == self._table_count:
                self._in_alt_table = True
                self._current_rank = "Option"
        elif tag == "tr" and (self._in_bis_table or self._in_alt_table):
            self._in_row = True
            self._cell_idx = -1
            self._current_item_id = None
            self._source_text = ""
        elif tag == "td" and self._in_row:
            self._in_cell = True
            self._cell_idx += 1
            self._cell_text = ""
            self._is_slot_cell = False
            self._has_strong = False
        elif tag == "strong" and self._in_cell and self._cell_idx == 0:
            self._in_strong = True
            self._strong_text = ""
            self._has_strong = True
        elif tag == "li" and self._in_cell:
            self._in_li = True
            self._current_item_id = None
            self._current_item_name = ""
            self._source_text = ""
        elif tag == "a" and self._in_cell:
            wowhead = attr.get("data-wowhead", "")
            css_class = attr.get("class", "")
            # Only capture item links (not npc/quest/spell links)
            if "item=" in wowhead and css_class not in (
                "npc",
                "quest",
                "spell",
                "zone",
                "achievement",
            ):
                m = re.search(r"item=(\d+)", wowhead)
                if m:
                    if self._in_li and self._current_item_id is None:
                        self._current_item_id = int(m.group(1))
                    elif not self._in_li and self._cell_idx == 1:
                        # Direct item in cell (no <li> wrapper) — paladin format
                        self._current_item_id = int(m.group(1))

    def handle_endtag(self, tag: str):
        if tag == "h2":
            self._in_h2 = False
            h = self._heading_text.lower()
            if "best in slot" in h:
                self._bis_table_idx = self._table_count + 1
            elif "other useful" in h:
                self._alt_table_idx = self._table_count + 1
        elif tag == "h3":
            self._in_h3 = False
            if "best in slot" in self._heading_text.lower():
                # Next table is the BiS table
                self._bis_table_idx = self._table_count + 1
        elif tag == "h4":
            self._in_h4 = False
            if "other useful" in self._heading_text.lower():
                # Next table is the alternatives table
                self._alt_table_idx = self._table_count + 1
        elif tag == "table":
            self._in_bis_table = False
            self._in_alt_table = False
        elif tag == "tr" and self._in_row:
            self._in_row = False
            # Flush any item captured directly in a cell (no <li> wrapper)
            if self._current_item_id and not self._in_li:
                self._add_item()
                self._current_item_id = None
        elif tag == "td" and self._in_cell:
            self._in_cell = False
            if self._in_strong and self._cell_idx == 0:
                self._in_strong = False
            # Detect slot names from plain <td>SlotName</td> (no <strong>)
            if self._cell_idx == 0 and not self._has_strong:
                slot_name = self._cell_text.strip().lower()
                mapped = SLOT_NAME_MAP.get(slot_name)
                if mapped:
                    self._current_slot = mapped
        elif tag == "strong" and self._in_strong:
            self._in_strong = False
            if self._cell_idx == 0:
                slot_name = self._strong_text.strip().lower()
                mapped = SLOT_NAME_MAP.get(slot_name)
                if mapped:
                    self._current_slot = mapped
        elif tag == "li" and self._in_li:
            self._in_li = False
            self._add_item()

    def handle_data(self, data: str):
        if self._in_h2 or self._in_h3 or self._in_h4:
            self._heading_text += data
        if self._in_strong and self._cell_idx == 0:
            self._strong_text += data
        if self._in_cell:
            self._cell_text += data
        if self._in_li:
            self._source_text += data
        elif self._in_cell and self._cell_idx == 2:
            # Source column text for non-li format
            self._source_text += data

    def handle_entityref(self, name: str):
        if self._in_li:
            char = {"amp": "&", "lt": "<", "gt": ">", "apos": "'", "quot": '"'}.get(
                name, f"&{name};"
            )
            self._source_text += char

    def _add_item(self):
        if not self._current_item_id or not self._current_slot:
            return

        # Extract item name from source text — it's the text of the first item link
        # We need to re-parse to get it. Use a simpler approach: look at collected text.
        # The source_text contains everything including the item name.
        # We'll get the name from the item DB or from the source text.
        # For now, store what we have and let the item name come from the link text.

        item: dict[str, str | int] = {
            "rank": self._current_rank,
            "item_id": self._current_item_id,
            "source": " ".join(self._source_text.split()),  # normalize whitespace
        }
        self.results.setdefault(self._current_slot, []).append(item)


class ItemNameParser(HTMLParser):
    """Second-pass parser to extract item names from <a> tags with item data-wowhead."""

    def __init__(self):
        super().__init__()
        self.names: dict[int, str] = {}
        self._in_item_link = False
        self._current_id: int | None = None
        self._current_name = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr: dict[str, str] = {k: v or "" for k, v in attrs}
        if tag == "a":
            wowhead = attr.get("data-wowhead", "")
            css_class = attr.get("class", "")
            if "item=" in wowhead and css_class not in (
                "npc",
                "quest",
                "spell",
                "zone",
                "achievement",
            ):
                m = re.search(r"item=(\d+)", wowhead)
                if m:
                    self._in_item_link = True
                    self._current_id = int(m.group(1))
                    self._current_name = ""

    def handle_endtag(self, tag: str):
        if tag == "a" and self._in_item_link:
            self._in_item_link = False
            if self._current_id and self._current_name:
                # Only store first occurrence (primary item, not token)
                if self._current_id not in self.names:
                    self.names[self._current_id] = self._current_name.strip()

    def handle_data(self, data: str):
        if self._in_item_link:
            self._current_name += data


def parse_phase_file(
    filepath: Path,
) -> dict[str, list[dict[str, str | int]]]:
    html = filepath.read_text(encoding="utf-8")

    # First pass: extract item names
    name_parser = ItemNameParser()
    name_parser.feed(html)

    # Second pass: extract structured data
    parser = IcyVeinsParser()
    parser.feed(html)

    # Merge names into results
    for slot_items in parser.results.values():
        for item in slot_items:
            item_id = item.get("item_id")
            if isinstance(item_id, int) and item_id in name_parser.names:
                item["name"] = name_parser.names[item_id]

    return parser.results


def main():
    parser = argparse.ArgumentParser(
        description="Parse Icy Veins Shaman BiS HTML into JSON."
    )
    parser.add_argument(
        "--spec",
        default="resto-shaman",
        help="Spec to parse: resto, ele (or elemental). Default: resto-shaman.",
    )
    parser.add_argument("--output", default=None, help="Override output JSON path.")
    args = parser.parse_args()

    spec = resolve_spec(args.spec)
    output_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT / "output" / spec / "iv_bis_gear.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read current phase
    current_phase_file = PROJECT_ROOT / "data" / "current-phase.txt"
    current_phase = (
        current_phase_file.read_text(encoding="utf-8").strip()
        if current_phase_file.exists()
        else None
    )

    # Parse all phase files
    result: dict[str, str | dict] = {}
    if current_phase:
        result["current_phase"] = current_phase
    source_dir = PROJECT_ROOT / "sources" / "icy-veins" / spec
    phase_files = sorted(source_dir.glob("phase-*.html"))
    if not phase_files:
        print(f"No phase-*.html files found in {source_dir}.")
        sys.exit(1)

    phases: dict[str, dict] = {}
    for pf in phase_files:
        phase_name = pf.stem  # e.g. "phase-0", "phase-1"
        print(f"Parsing {pf.name}...")
        slots = parse_phase_file(pf)
        phases[phase_name] = slots

    result["phases"] = phases

    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWrote {output_path} with {len(phases)} phases.")
    for phase, slots in phases.items():
        total_items = sum(len(items) for items in slots.values())
        print(f"  {phase}: {len(slots)} slots, {total_items} items")


if __name__ == "__main__":
    main()
