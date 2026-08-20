"""Per-item release phases from Wowhead's TBC Classic tooltip data.

Wowhead's tooltip endpoint (the same one their on-site tooltips use) tags each
item with its release phase for the classic progression — `dataEnv=5` is TBC
Classic, whose phase numbering matches the Anniversary phases. This catches
later-phase items that raid lootmaps can't see: badge-vendor gear, crafted
additions, and anything else patch-gated (e.g. Carved Witch Doctor's Stick,
a 2.3 badge wand, is tagged Phase 4).

The cache (`data/meta/item_phases.json`) maps item id -> phase int (or null if
wowhead shows no phase tag). Build/refresh with `bis-pipeline item-phases`;
only ids missing from the cache are fetched.
"""

import json
import logging
import re
import time

import httpx

from .config import META_DIR, RAW_DIR

log = logging.getLogger(__name__)

ITEM_PHASES_PATH = META_DIR / "item_phases.json"
TOOLTIP_URL = "https://nether.wowhead.com/tooltip/item/{item_id}?dataEnv=5&locale=0"
PHASE_RE = re.compile(r'whtt-extra">Phase (\d+)<')
# Only items worn at least this often can ever pass the aggregation floors.
MIN_WEAR_COUNT = 5


def load_item_phases() -> dict[str, int | None] | None:
    if ITEM_PHASES_PATH.exists():
        return json.loads(ITEM_PHASES_PATH.read_text())
    return None


def _worn_item_ids() -> set[int]:
    """One scan of the raw cache: every item id worn >= MIN_WEAR_COUNT times."""
    counts: dict[int, int] = {}
    for page_file in RAW_DIR.rglob("page-*.json"):
        for row in json.loads(page_file.read_text())["rankings"]:
            for gear in row.get("gear", []):
                item_id = gear.get("id")
                if item_id:
                    counts[item_id] = counts.get(item_id, 0) + 1
    return {i for i, n in counts.items() if n >= MIN_WEAR_COUNT}


def build_item_phases() -> dict[str, int | None]:
    """Fetch phase tags for every relevant item id not yet cached."""
    from .config import ZONES
    from .lootmap import build_lootmap, load_lootmap

    cache: dict[str, int | None] = load_item_phases() or {}

    ids = _worn_item_ids()
    for zone_tag in ZONES:
        lootmap = load_lootmap(zone_tag) or build_lootmap(zone_tag)
        for enc in lootmap.values():
            ids.update(enc["items"])

    missing = sorted(i for i in ids if str(i) not in cache)
    log.info("item phases: %d relevant ids, %d to fetch", len(ids), len(missing))

    client = httpx.Client(timeout=30.0, headers={"User-Agent": "Mozilla/5.0"})
    for n, item_id in enumerate(missing, 1):
        try:
            resp = client.get(TOOLTIP_URL.format(item_id=item_id))
            if resp.status_code == 200:
                match = PHASE_RE.search(resp.json().get("tooltip", ""))
                cache[str(item_id)] = int(match.group(1)) if match else None
            else:
                log.warning("item %d: HTTP %d — left unknown", item_id, resp.status_code)
                cache[str(item_id)] = None
        except httpx.HTTPError as exc:
            log.warning("item %d: %s — left unknown", item_id, exc)
            cache[str(item_id)] = None
        if n % 250 == 0:
            log.info("item phases: %d/%d fetched", n, len(missing))
            ITEM_PHASES_PATH.write_text(json.dumps(cache, indent=0))
        time.sleep(0.2)  # be polite

    ITEM_PHASES_PATH.write_text(json.dumps(cache, indent=0))
    tagged = sum(1 for v in cache.values() if v)
    log.info(
        "item phases cached: %d ids (%d phase-tagged) -> %s", len(cache), tagged, ITEM_PHASES_PATH
    )
    return cache
