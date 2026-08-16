"""Map WCL encounters to their loot tables via the cmangos DB.

Creature matching is by encounter name against creature_template (only rows
with a lootid), with per-encounter overrides where the loot-carrying creature
differs from the encounter name (council fights, multi-phase bosses).

Loot expansion follows the mangos convention: `mincountOrRef < 0` points into
reference_loot_template at entry = -mincountOrRef (expanded recursively).

Kept items: Quality >= 4 (epics incl. tier tokens), or Quality 3 weapons and
armor. This drops Badges of Justice, quest objectives, and holiday junk.
"""

import json
import logging
import sqlite3

from .config import META_DIR, ZONES
from .enrich import CMANGOS_DB

log = logging.getLogger(__name__)

# encounter id -> creature entries carrying the loot, where name-match fails.
CREATURE_OVERRIDES: dict[int, list[int]] = {
    606: [23420],  # Reliquary of Souls -> Essence of Anger (final essence)
    # Illidari Council: items ride on Zerevor (ref 36135), the T6 legs token
    # group (ref 36136) on the other three — Gathios covers it once.
    608: [22949, 22950],
}


def _keep(quality: int, item_class: int) -> bool:
    return quality >= 4 or (quality == 3 and item_class in (2, 4))


def _expand_loot(con: sqlite3.Connection, loot_ids: list[int]) -> set[int]:
    items: set[int] = set()
    seen_refs: set[int] = set()

    def walk(table: str, entries: list[int]) -> None:
        if not entries:
            return
        placeholders = ",".join("?" * len(entries))
        rows = con.execute(
            f"SELECT item, mincountOrRef FROM {table} WHERE entry IN ({placeholders})",
            entries,
        ).fetchall()
        refs = []
        for item, mincount_or_ref in rows:
            if mincount_or_ref < 0:
                ref = -mincount_or_ref
                if ref not in seen_refs:
                    seen_refs.add(ref)
                    refs.append(ref)
            else:
                items.add(item)
        walk("reference_loot_template", refs)

    walk("creature_loot_template", loot_ids)
    return items


def build_lootmap(zone_tag: str) -> dict:
    zone = ZONES[zone_tag]
    encounters = json.loads((META_DIR / f"encounters-{zone['zone_id']}.json").read_text())
    con = sqlite3.connect(CMANGOS_DB)

    result: dict[str, dict] = {}
    for enc in encounters:
        if enc["id"] in CREATURE_OVERRIDES:
            creatures = CREATURE_OVERRIDES[enc["id"]]
        else:
            creatures = [
                row[0]
                for row in con.execute(
                    "SELECT lootid FROM creature_template WHERE name = ? AND lootid > 0",
                    (enc["name"],),
                )
            ]
        if not creatures:
            log.warning("no loot creature found for encounter %d %s", enc["id"], enc["name"])
            continue
        candidates = _expand_loot(con, creatures)
        kept = []
        if candidates:
            placeholders = ",".join("?" * len(candidates))
            kept = [
                entry
                for entry, quality, item_class in con.execute(
                    f"SELECT entry, Quality, class FROM item_template "
                    f"WHERE entry IN ({placeholders})",
                    sorted(candidates),
                )
                if _keep(quality, item_class)
            ]
        result[str(enc["id"])] = {"name": enc["name"], "items": sorted(kept)}
        log.info("lootmap %s: %d items", enc["name"], len(kept))

    out_path = META_DIR / f"lootmap-{zone_tag}.json"
    out_path.write_text(json.dumps(result, indent=1))
    return result


def load_lootmap(zone_tag: str) -> dict | None:
    path = META_DIR / f"lootmap-{zone_tag}.json"
    return json.loads(path.read_text()) if path.exists() else None


def later_phase_items(zone_tag: str) -> set[int]:
    """All raid-dropped item ids from zones of a LATER anniversary phase.

    Used to purge poisoned ranking rows: a player wearing any of these was
    logged after the next tier released and does not represent this phase.
    """
    own_phase = ZONES[zone_tag]["anniversary_phase"]
    ids: set[int] = set()
    for other_tag, other in ZONES.items():
        if other["anniversary_phase"] > own_phase:
            other_map = load_lootmap(other_tag) or build_lootmap(other_tag)
            for enc in other_map.values():
                ids.update(enc["items"])
    return ids
