"""Shared constants and utilities used across bis_gear modules."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Spec resolution
# ---------------------------------------------------------------------------

SPEC_ALIASES: dict[str, str] = {
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
    """Normalize a spec alias to its canonical slug."""
    key = raw.strip().lower()
    if key not in SPEC_ALIASES:
        print(f"Unknown spec '{raw}'. Use: resto, ele, prot.")
        sys.exit(1)
    return SPEC_ALIASES[key]


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def load_current_phase() -> str | None:
    """Read current-phase.txt and return the phase string, or None if missing."""
    phase_file = PROJECT_ROOT / "data" / "current-phase.txt"
    if not phase_file.exists():
        return None
    return phase_file.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

DB_PATH = PROJECT_ROOT / "sources" / "cmangos-tbc-db" / "tbcmangos.sqlite"


def get_db_conn() -> sqlite3.Connection:
    """Open a connection to the cmangos TBC SQLite database."""
    if not DB_PATH.exists():
        print(f"Error: TBC database not found at {DB_PATH}", file=sys.stderr)
        print(
            "Download from: https://github.com/cmangos/tbc-db/releases",
            file=sys.stderr,
        )
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

QUALITY_NAMES: dict[int, str] = {
    0: "Poor",
    1: "Common",
    2: "Uncommon",
    3: "Rare",
    4: "Epic",
    5: "Legendary",
}

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


# ---------------------------------------------------------------------------
# Character loading (WSE and classic formats)
# ---------------------------------------------------------------------------


def load_character(
    path: str | Path,
    *,
    item_name_resolver: dict[int, str] | None = None,
) -> dict:
    """Load character JSON from *path* (or ``"-"`` for stdin).

    Handles both the WowSims Exporter (WSE) format and the classic
    ``{"character": {...}}`` format.

    Parameters
    ----------
    path:
        Filesystem path or ``"-"`` for stdin.
    item_name_resolver:
        Optional ``{item_id: name}`` dict used to resolve item names for
        WSE imports (check_gear passes the wowsims item DB here).
    """
    if str(path) == "-":
        data = json.load(sys.stdin)
    else:
        p = Path(path)
        if not p.exists():
            alt = PROJECT_ROOT / "data" / p.name
            if alt.exists():
                p = alt
        data = json.loads(p.read_text(encoding="utf-8"))

    # Detect WSE format (has gear.items)
    if "gear" in data and "items" in data.get("gear", {}):
        return _normalize_wse(data, item_name_resolver)

    return data if "character" not in data else data["character"]


def _normalize_wse(
    data: dict,
    item_name_resolver: dict[int, str] | None,
) -> dict:
    """Convert WowSims Exporter JSON to the internal character format."""
    items = data["gear"]["items"]
    equipped: list[dict] = []
    for i, item in enumerate(items):
        if item is None or i >= len(WSE_SLOT_ORDER):
            continue
        item_id = item.get("id", 0)
        if not item_id:
            continue
        name = (
            item_name_resolver.get(item_id, f"ID:{item_id}")
            if item_name_resolver
            else f"ID:{item_id}"
        )
        equipped.append(
            {
                "slot": i + 1,
                "slotName": WSE_SLOT_ORDER[i],
                "itemId": item_id,
                "itemName": name,
            }
        )
    result: dict = {
        "name": data.get("name", "Unknown"),
        "class": data.get("class", ""),
        "race": data.get("race", ""),
        "talents": data.get("talents", ""),
        "equippedItems": equipped,
        "reputations": [],
        "_wse_raw": data,  # Preserve for gem/enchant parsing
    }
    return result
