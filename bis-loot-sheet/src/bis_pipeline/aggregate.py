"""Aggregate raw ranking pages into per-spec, per-slot item usage distributions.

Reads the US/EU region slices from data/raw/ (the basic data set; when the
full-depth data lands, SATURATED region slices will be swapped for their
server slices here) and writes one JSON per zone to data/aggregated/.

Output shape (consumed by the web app and the prio generator):
  {
    "zone": "bt-hyjal", "zoneId": 1011, "partition": 4,
    "regions": ["US", "EU"], "maxPages": 5, "generatedAt": "...",
    "specs": {
      "Shaman-Enhancement": {
        "sampleSize": 13908,           # (character, boss) rows pooled phase-wide
        "slots": {
          "main_hand": [ {"id", "name", "quality", "icon", "count", "pct"}, ... ]
        }
      }
    }
  }

pct is count / sampleSize. Items below the floor (pct < 0.5% or count < 5) are
dropped here; the app applies the 2% display floor from docs/PLAN.md on top.
"""

import json
import logging
from collections import Counter
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

from .config import MAX_PAGE, META_DIR, RAW_DIR, REGIONS, ZONES

log = logging.getLogger(__name__)

AGGREGATED_DIR = RAW_DIR.parent / "aggregated"

# Gear array index -> slot key. Verified against live data (see docs/PLAN.md).
SLOT_BY_INDEX = {
    0: "head",
    1: "neck",
    2: "shoulder",
    # 3 = shirt, cosmetic — skipped
    4: "chest",
    5: "waist",
    6: "legs",
    7: "feet",
    8: "wrist",
    9: "hands",
    10: "ring",
    11: "ring",
    12: "trinket",
    13: "trinket",
    14: "back",
    15: "main_hand",
    16: "off_hand",
    17: "ranged",
}

MIN_PCT = 0.5
MIN_COUNT = 5


def _iter_pages(slice_dir: Path, max_pages: int):
    for page in range(1, max_pages + 1):
        page_file = slice_dir / f"page-{page:02d}.json"
        if not page_file.exists():
            return
        yield json.loads(page_file.read_text())


@cache
def _server_count(region: str) -> int:
    servers = json.loads((META_DIR / "regions_servers.json").read_text())
    return len(servers[region])


def _iter_slice(region_dir: Path, region: str, max_pages: int):
    """Yield pages for one (spec, region) slice.

    A SATURATED region slice is REPLACED by its per-server slices — but only
    when the server descent is complete (every server of the region has a
    `_done` marker). Mid-fetch, fall back to the capped region pages so a
    partial descent never undercounts relative to the basic set.
    """
    if (region_dir / "SATURATED").exists():
        server_dirs = sorted(region_dir.glob("server-*"))
        done = [d for d in server_dirs if (d / "_done").exists()]
        if server_dirs and len(done) == _server_count(region):
            for server_dir in done:
                if (server_dir / "SATURATED").exists():
                    log.warning("server slice saturated (>2000 rows capped): %s", server_dir)
                yield from _iter_pages(server_dir, MAX_PAGE)
            return
        log.warning(
            "%s: saturated but server descent incomplete (%d/%d) — using capped region pages",
            region_dir,
            len(done),
            _server_count(region),
        )
    yield from _iter_pages(region_dir, max_pages)


def aggregate_zone(zone_tag: str, max_pages: int) -> Path:
    zone = ZONES[zone_tag]
    zone_dir = RAW_DIR / f"zone-{zone['zone_id']}"
    specs: dict[str, dict] = {}

    # spec -> slot -> Counter of item id; plus one exemplar per item id for
    # name/quality/icon (WCL repeats them on every row).
    counts: dict[str, dict[str, Counter]] = {}
    items: dict[int, dict] = {}
    samples: Counter = Counter()

    for enc_dir in sorted(zone_dir.glob("enc-*")):
        # Pin to the configured partition — other partitions may exist on disk
        # (e.g. the progression-era p4 data kept for later comparisons).
        for spec_dir in sorted(
            p for p in enc_dir.glob(f"p{zone['partition']}/[A-Z]*") if p.is_dir()
        ):
            spec_key = spec_dir.name
            for region in REGIONS:
                for payload in _iter_slice(spec_dir / region, region, max_pages):
                    for row in payload["rankings"]:
                        samples[spec_key] += 1
                        for idx, gear in enumerate(row.get("gear", [])):
                            slot = SLOT_BY_INDEX.get(idx)
                            if slot is None or not gear.get("id"):
                                continue
                            counts.setdefault(spec_key, {}).setdefault(slot, Counter())[
                                gear["id"]
                            ] += 1
                            items.setdefault(
                                gear["id"], {k: gear[k] for k in ("name", "quality", "icon")}
                            )

    for spec_key, slots in sorted(counts.items()):
        sample = samples[spec_key]
        out_slots: dict[str, list[dict]] = {}
        for slot, counter in slots.items():
            entries = []
            for item_id, count in counter.most_common():
                pct = 100.0 * count / sample
                if pct < MIN_PCT or count < MIN_COUNT:
                    continue
                entries.append(
                    {"id": item_id, **items[item_id], "count": count, "pct": round(pct, 2)}
                )
            out_slots[slot] = entries
        specs[spec_key] = {"sampleSize": sample, "slots": out_slots}

    result = {
        "zone": zone_tag,
        "zoneId": zone["zone_id"],
        "partition": zone["partition"],
        "anniversaryPhase": zone["anniversary_phase"],
        "regions": list(REGIONS),
        "maxPages": max_pages,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "specs": specs,
    }
    AGGREGATED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AGGREGATED_DIR / f"{zone_tag}.json"
    out_path.write_text(json.dumps(result, indent=1))
    log.info(
        "aggregated %s: %d specs, %d total rows -> %s",
        zone_tag,
        len(specs),
        sum(samples.values()),
        out_path,
    )
    return out_path
