"""Adaptive ranking fetcher.

Slicing strategy (see docs/PLAN.md):
- Always filter by class AND spec — the BiS data is spec-based.
- Default slice: one query series per (encounter, partition, metric, region).
- If a region slice saturates (page 20 and still hasMorePages), descend to
  per-server slices within that region and REPLACE the region slice (ranking
  rows carry no server field, so cross-slice dedup is unreliable; replacement
  sidesteps it). A SATURATED marker file records the descent.

Cache layout (one raw API response per file, fully resumable):
  data/raw/zone-{zid}/enc-{eid}/p{partition}/{Class}-{Spec}/{region}/page-{NN}.json
  data/raw/.../{Class}-{Spec}/{region}/SATURATED            (descended marker)
  data/raw/.../{Class}-{Spec}/{region}/server-{slug}/page-{NN}.json
  A `_done` marker in each slice directory means the slice is complete.
"""

import json
import logging
from pathlib import Path

from .client import WCLClient
from .config import EXCLUDED_CLASSES, MAX_PAGE, RAW_DIR, ZONES, metric_for_spec
from .discovery import class_specs, regions_servers, zone_encounters

log = logging.getLogger(__name__)


def _rankings_query(
    encounter_id: int,
    partition: int,
    class_name: str,
    spec_name: str,
    metric: str,
    page: int,
    region: str | None = None,
    server: str | None = None,
) -> str:
    args = [
        f"partition: {partition}",
        # The API wants slug form: "Beast Mastery" -> "BeastMastery".
        f'className: "{class_name.replace(" ", "")}"',
        f'specName: "{spec_name.replace(" ", "")}"',
        f"metric: {metric}",
        f"page: {page}",
        "includeCombatantInfo: true",
    ]
    if region:
        args.append(f'serverRegion: "{region}"')
    if server:
        args.append(f'serverSlug: "{server}"')
    return (
        f"worldData {{ encounter(id: {encounter_id}) {{ characterRankings({', '.join(args)}) }} }}"
    )


class SliceFetcher:
    """Fetches one slice (a page series under a fixed filter combination)."""

    def __init__(self, client: WCLClient) -> None:
        self.client = client
        self.pages_fetched = 0

    def fetch_slice(
        self,
        slice_dir: Path,
        encounter_id: int,
        partition: int,
        class_name: str,
        spec_name: str,
        metric: str,
        region: str | None = None,
        server: str | None = None,
        probe_first: bool = False,
    ) -> bool:
        """Fetch all pages for one filter combination. Returns True if saturated.

        With probe_first (used for populous regions), page 20 is fetched before
        pages 1-19: a saturated slice gets replaced by server slices anyway, so
        detecting saturation up front skips 19 redundant page fetches.
        """
        done_marker = slice_dir / "_done"
        if done_marker.exists():
            return (slice_dir / "SATURATED").exists()

        slice_dir.mkdir(parents=True, exist_ok=True)

        if probe_first:
            payload = self._get_page(
                slice_dir,
                encounter_id,
                partition,
                class_name,
                spec_name,
                metric,
                MAX_PAGE,
                region,
                server,
            )
            if payload and payload.get("rankings") and payload.get("hasMorePages"):
                (slice_dir / "SATURATED").touch()
                done_marker.touch()
                return True

        saturated = False
        for page in range(1, MAX_PAGE + 1):
            payload = self._get_page(
                slice_dir,
                encounter_id,
                partition,
                class_name,
                spec_name,
                metric,
                page,
                region,
                server,
            )
            if payload is None or not payload.get("rankings"):
                break
            if not payload.get("hasMorePages"):
                break
        else:
            saturated = True

        if saturated:
            (slice_dir / "SATURATED").touch()
        done_marker.touch()
        return saturated

    def _get_page(
        self,
        slice_dir: Path,
        encounter_id: int,
        partition: int,
        class_name: str,
        spec_name: str,
        metric: str,
        page: int,
        region: str | None,
        server: str | None,
    ) -> dict | None:
        """Fetch one page (cached). Returns None on error or empty page."""
        page_file = slice_dir / f"page-{page:02d}.json"
        if page_file.exists():
            return json.loads(page_file.read_text())
        query = _rankings_query(
            encounter_id, partition, class_name, spec_name, metric, page, region, server
        )
        data = self.client.query(query)
        payload = data["worldData"]["encounter"]["characterRankings"]
        if payload.get("error"):
            # Common for class/spec combos with no rankings in this game
            # version; treat as an empty slice but keep a record.
            log.warning("rankings error for %s: %s", slice_dir, payload["error"])
            return None
        if not payload.get("rankings"):
            return None  # empty page: don't persist noise files
        page_file.write_text(json.dumps(payload))
        self.pages_fetched += 1
        return payload


def fetch_encounter(
    client: WCLClient,
    zone_tag: str,
    encounter: dict,
    specs: list[dict],
    servers_by_region: dict[str, list[str]],
    regions: list[str],
) -> dict:
    """Fetch every spec x region slice for one encounter, descending on saturation."""
    zone = ZONES[zone_tag]
    zone_id, partition = zone["zone_id"], zone["partition"]
    enc_dir = RAW_DIR / f"zone-{zone_id}" / f"enc-{encounter['id']}" / f"p{partition}"
    fetcher = SliceFetcher(client)
    stats = {"slices": 0, "saturated": 0, "server_slices": 0}

    for pair in specs:
        class_name, spec_name = pair["class"], pair["spec"]
        metric = metric_for_spec(spec_name)
        spec_dir = enc_dir / f"{class_name}-{spec_name}"
        for region in regions:
            region_dir = spec_dir / region
            stats["slices"] += 1
            saturated = fetcher.fetch_slice(
                region_dir,
                encounter["id"],
                partition,
                class_name,
                spec_name,
                metric,
                region=region,
                # Populous regions frequently exceed the 2,000-row window; probe
                # page 20 first there to skip straight to server descent.
                probe_first=region in {"US", "EU", "CN"},
            )
            if saturated:
                stats["saturated"] += 1
                log.info(
                    "SATURATED: %s %s/%s %s — descending to %d servers",
                    encounter["name"],
                    class_name,
                    spec_name,
                    region,
                    len(servers_by_region[region]),
                )
                for slug in servers_by_region[region]:
                    server_dir = region_dir / f"server-{slug}"
                    stats["server_slices"] += 1
                    fetcher.fetch_slice(
                        server_dir,
                        encounter["id"],
                        partition,
                        class_name,
                        spec_name,
                        metric,
                        region=region,
                        server=slug,
                    )
    stats["pages_fetched"] = fetcher.pages_fetched
    return stats


def fetch_zone(
    client: WCLClient,
    zone_tag: str,
    only_encounter: int | None = None,
) -> None:
    zone = ZONES[zone_tag]
    encounters = zone_encounters(client, zone["zone_id"])
    specs = [p for p in class_specs(client) if p["class"] not in EXCLUDED_CLASSES]
    servers_by_region = regions_servers(client)
    regions = list(servers_by_region.keys())
    log.info(
        "zone %s (id %d, partition %d): %d encounters, %d class/spec pairs, regions %s",
        zone_tag,
        zone["zone_id"],
        zone["partition"],
        len(encounters),
        len(specs),
        regions,
    )
    for encounter in encounters:
        if only_encounter is not None and encounter["id"] != only_encounter:
            continue
        stats = fetch_encounter(client, zone_tag, encounter, specs, servers_by_region, regions)
        rl = client.last_rate_limit or {}
        log.info(
            "%s done: %s | points spent this hour: %.1f",
            encounter["name"],
            stats,
            rl.get("pointsSpentThisHour", -1),
        )
