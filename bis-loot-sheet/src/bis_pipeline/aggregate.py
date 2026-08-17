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

# Player bands. top10/mid50/all are parse-percentile cuts over the full
# population; top2000 is source-based — the capped region windows (pages 1-20
# per US/EU region) exactly as WCL's site shows them, no server descent.
BANDS = ("top10", "top2000", "mid50", "all")


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
    from .lootmap import later_phase_items

    zone = ZONES[zone_tag]
    zone_dir = RAW_DIR / f"zone-{zone['zone_id']}"
    specs: dict[str, dict] = {}

    # WCL's late-TBC partitions merge eras ("P3.5 & P4"), so rows logged after
    # the next tier released can wear next-phase gear. Any row containing a
    # later-phase raid drop is discarded entirely — the distributions must
    # only describe loadouts achievable within this phase (Xyrec directive).
    poison = later_phase_items(zone_tag)

    def iter_kept_rows():
        """Yield (enc_id, spec_key, row) for every phase-pure ranking row."""
        for enc_dir in sorted(zone_dir.glob("enc-*")):
            enc_id = int(enc_dir.name.split("-")[1])
            # Pin to the configured partition — other partitions may exist on
            # disk (e.g. the progression-era p4 data kept for comparisons).
            for spec_dir in sorted(
                p for p in enc_dir.glob(f"p{zone['partition']}/[A-Z]*") if p.is_dir()
            ):
                for region in REGIONS:
                    for payload in _iter_slice(spec_dir / region, region, max_pages):
                        for row in payload["rankings"]:
                            if any(g.get("id") in poison for g in row.get("gear", [])):
                                dropped_rows[spec_dir.name] += 1
                                continue
                            yield enc_id, spec_dir.name, row

    dropped_rows: Counter = Counter()

    # Pass 1: per (spec, encounter) parse-amount thresholds for the bands.
    # Full populations are on disk, so the percentiles are exact.
    amounts: dict[tuple[int, str], list[float]] = {}
    for enc_id, spec_key, row in iter_kept_rows():
        amounts.setdefault((enc_id, spec_key), []).append(row.get("amount", 0.0))
    thresholds: dict[tuple[int, str], tuple[float, float, float]] = {}
    for key, values in amounts.items():
        values.sort()
        n = len(values)
        thresholds[key] = (
            values[int(0.90 * (n - 1))],  # p90: top-10% floor
            values[int(0.25 * (n - 1))],  # p25 \ mid-50% window
            values[int(0.75 * (n - 1))],  # p75 /
        )
    amounts.clear()
    dropped_rows.clear()  # counted again (identically) in pass 2

    # Pass 2: bucket rows into bands and count item usage per band.
    # band -> spec -> slot -> Counter; band -> spec -> sample size.
    counts: dict[str, dict[str, dict[str, Counter]]] = {b: {} for b in BANDS}
    samples: dict[str, Counter] = {b: Counter() for b in BANDS}
    items: dict[int, dict] = {}
    # Per-encounter stats for the app's overview page: kept-row counts and
    # kill-duration histograms (15s bins, milliseconds in the raw rows).
    DURATION_BIN_MS = 15_000
    enc_names = {
        e["id"]: e["name"]
        for e in json.loads((META_DIR / f"encounters-{zone['zone_id']}.json").read_text())
    }
    enc_rows: Counter = Counter()
    enc_durations: dict[int, Counter] = {}
    enc_duration_sums: Counter = Counter()

    for enc_id, spec_key, row in iter_kept_rows():
        p90, p25, p75 = thresholds[(enc_id, spec_key)]
        amount = row.get("amount", 0.0)
        bands = ["all"]
        if amount >= p90:
            bands.append("top10")
        if p25 <= amount <= p75:
            bands.append("mid50")

        enc_rows[enc_id] += 1
        duration = row.get("duration")
        if duration:
            bin_s = (duration // DURATION_BIN_MS) * 15
            enc_durations.setdefault(enc_id, Counter())[bin_s] += 1
            enc_duration_sums[enc_id] += duration

        for band in bands:
            samples[band][spec_key] += 1
        for idx, gear in enumerate(row.get("gear", [])):
            slot = SLOT_BY_INDEX.get(idx)
            if slot is None or not gear.get("id"):
                continue
            for band in bands:
                counts[band].setdefault(spec_key, {}).setdefault(slot, Counter())[gear["id"]] += 1
            items.setdefault(gear["id"], {k: gear[k] for k in ("name", "quality", "icon")})

    # Pass 3: the "top2000" band — region pages only (contiguous from page 1),
    # skipping the server-descent data entirely. Poison-filtered like the rest.
    for enc_dir in sorted(zone_dir.glob("enc-*")):
        for spec_dir in sorted(
            p for p in enc_dir.glob(f"p{zone['partition']}/[A-Z]*") if p.is_dir()
        ):
            spec_key = spec_dir.name
            for region in REGIONS:
                for payload in _iter_pages(spec_dir / region, MAX_PAGE):
                    for row in payload["rankings"]:
                        if any(g.get("id") in poison for g in row.get("gear", [])):
                            continue
                        samples["top2000"][spec_key] += 1
                        for idx, gear in enumerate(row.get("gear", [])):
                            slot = SLOT_BY_INDEX.get(idx)
                            if slot is None or not gear.get("id"):
                                continue
                            counts["top2000"].setdefault(spec_key, {}).setdefault(slot, Counter())[
                                gear["id"]
                            ] += 1
                            items.setdefault(
                                gear["id"], {k: gear[k] for k in ("name", "quality", "icon")}
                            )

    for spec_key in sorted(counts["all"]):
        out_bands: dict[str, dict] = {}
        for band in BANDS:
            sample = samples[band][spec_key]
            out_slots: dict[str, list[dict]] = {}
            for slot, counter in counts[band].get(spec_key, {}).items():
                entries = []
                for item_id, count in counter.most_common():
                    pct = 100.0 * count / max(1, sample)
                    if pct < MIN_PCT or count < MIN_COUNT:
                        continue
                    entries.append(
                        {"id": item_id, **items[item_id], "count": count, "pct": round(pct, 2)}
                    )
                out_slots[slot] = entries
            out_bands[band] = {"sampleSize": sample, "slots": out_slots}
        specs[spec_key] = {"bands": out_bands}

    stats = {
        "rowsKept": sum(samples["all"].values()),
        "rowsDropped": sum(dropped_rows.values()),
        "encounters": {
            str(eid): {
                "name": enc_names.get(eid, str(eid)),
                "rows": enc_rows[eid],
                "avgKillMs": int(
                    enc_duration_sums[eid] / max(1, sum(enc_durations.get(eid, Counter()).values()))
                ),
                # sparse histogram: [bin start in seconds, kill count]
                "durations": sorted(enc_durations.get(eid, Counter()).items()),
            }
            for eid in sorted(enc_rows)
        },
    }

    result = {
        "zone": zone_tag,
        "stats": stats,
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
    total_dropped = sum(dropped_rows.values())
    total_kept = sum(samples["all"].values())
    log.info(
        "aggregated %s: %d specs, %d rows kept, %d rows dropped (%.1f%%) for "
        "wearing later-phase raid gear -> %s",
        zone_tag,
        len(specs),
        total_kept,
        total_dropped,
        100.0 * total_dropped / max(1, total_kept + total_dropped),
        out_path,
    )
    return out_path
