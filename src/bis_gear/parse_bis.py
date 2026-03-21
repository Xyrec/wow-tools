"""
Parses TBC Shaman BiS HTML files into a structured JSON file.

Usage:
    bis-parse --spec resto
    bis-parse --spec ele
    bis-parse --spec resto --output custom_output.json

Spec aliases: resto, resto-shaman | ele, elemental, elemental-shaman
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def resolve_spec(raw: str) -> str:
    """Normalize spec alias to canonical slug."""
    aliases = {
        "resto": "resto-shaman",
        "resto-shaman": "resto-shaman",
        "ele": "elemental-shaman",
        "elemental": "elemental-shaman",
        "elemental-shaman": "elemental-shaman",
        "prot": "prot-paladin",
        "protection": "prot-paladin",
        "prot-paladin": "prot-paladin",
    }
    key = raw.strip().lower()
    if key not in aliases:
        print(f"Unknown spec '{raw}'. Use: resto, ele, prot.")
        sys.exit(1)
    return aliases[key]


class BisTableParser(HTMLParser):
    """Parses the BiS HTML files extracting gear slot tables."""

    def __init__(self):
        super().__init__()
        self.results: dict[str, list[dict[str, str | int]]] = {}

        # Tracking state
        self._current_slot: str | None = None
        self._in_table = False
        self._in_row = False
        self._cells: list[str] = []
        self._cell_idx = -1
        self._in_cell = False
        self._cell_text = ""
        self._is_header_row = False

        # Item link state (per-row, captured from cell index 1)
        self._row_item_href: str | None = None
        self._current_item_href: str | None = None

        # For slot detection from h3 tags
        self._in_h3 = False
        self._h3_id: str | None = None
        self._h3_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr = dict(attrs)

        if tag == "h3":
            self._in_h3 = True
            self._h3_id = attr.get("id", "")
            self._h3_text = ""
        elif tag == "table":
            self._in_table = True
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._cells = []
            self._is_header_row = False
            self._row_item_href = None
        elif tag == "td" and self._in_row:
            self._in_cell = True
            self._cell_text = ""
            self._current_item_href = None
            if attr.get("data-background") == "c7":
                self._is_header_row = True
        elif tag == "a" and self._in_cell:
            href = attr.get("href", "")
            if attr.get("data-entity") == "item" and href:
                self._current_item_href = href

    def handle_endtag(self, tag: str):
        if tag == "h3":
            self._in_h3 = False
            slot = self._normalize_slot(self._h3_id, self._h3_text)
            if slot and not slot.startswith("other-"):
                self._current_slot = slot
        elif tag == "table":
            self._in_table = False
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if not self._is_header_row and self._cells and self._current_slot:
                self._add_item()
        elif tag == "td" and self._in_cell:
            self._in_cell = False
            cell_index = len(self._cells)
            self._cells.append(self._cell_text.strip())
            # Capture item link info from the Item column (index 1)
            if cell_index == 1 and self._current_item_href:
                self._row_item_href = self._current_item_href

    def handle_data(self, data: str):
        if self._in_h3:
            self._h3_text += data
        if self._in_cell:
            self._cell_text += data

    # Normalize wowhead h3 IDs to canonical slot keys
    _SLOT_NORMALIZE: dict[str, str] = {
        "shoulder": "shoulders",
        "shield": "shields",
        "libram": "librams",
    }

    def _normalize_slot(self, h3_id: str | None, h3_text: str) -> str | None:
        if not h3_id:
            return None
        skip = {"aldor-vs-scryer", "best-in-slot-gear", "changelog"}
        # Skip non-slot sections and sub-category headers
        if (
            h3_id in skip
            or h3_id.startswith("best-in-slot")
            or h3_id.startswith("other-")
            or h3_id.startswith("crit-")
            or h3_id.startswith("stamina-")
            or h3_id.startswith("threat-")
        ):
            return None
        return self._SLOT_NORMALIZE.get(h3_id, h3_id)

    def _normalize_rank(self, raw_rank: str) -> str:
        """Normalize rank text to BiS/Option."""
        r = raw_rank.lower().strip()
        if r in ("rank", ""):
            return ""  # header row
        if r == "bis" or r.startswith("best"):
            return "BiS"
        if r in ("alternative", "option") or r.startswith("alternative"):
            return "Option"
        return "Option"  # treat unknown ranks as options

    def _add_item(self):
        if len(self._cells) < 2:
            return

        raw_rank = self._cells[0] if self._cells else ""
        rank = self._normalize_rank(raw_rank)
        if not rank:
            return  # skip header rows

        source = self._cells[2] if len(self._cells) > 2 else ""
        item_name = self._cells[1] if len(self._cells) > 1 else ""

        item_id = None
        if self._row_item_href:
            m = re.search(r"/item=(\d+)", self._row_item_href)
            if m:
                item_id = int(m.group(1))

        item: dict[str, str | int] = {
            "rank": rank,
            "name": item_name,
            "source": " ".join(source.split()),
        }
        if item_id:
            item["item_id"] = item_id

        if self._current_slot is not None:
            self.results.setdefault(self._current_slot, []).append(item)


def parse_phase_file(filepath: Path) -> dict[str, list[dict[str, str | int]]]:
    parser = BisTableParser()
    parser.feed(filepath.read_text(encoding="utf-8"))
    return parser.results


def main():
    parser = argparse.ArgumentParser(description="Parse Shaman BiS HTML into JSON.")
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
        else PROJECT_ROOT / "output" / spec / "bis_gear.json"
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
    result = {}
    if current_phase:
        result["current_phase"] = current_phase

    source_dir = PROJECT_ROOT / "sources" / "wowhead" / spec
    phase_files = sorted(source_dir.glob("phase-*.html"))
    if not phase_files:
        print(f"No phase-*.html files found in {source_dir}.")
        sys.exit(1)

    phases = {}
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
