"""CLI entry point: uv run bis-pipeline <command>."""

import argparse
import logging

from .aggregate import aggregate_zone
from .client import WCLClient
from .config import PHASES, ZONES
from .discovery import class_specs, regions_servers, zone_encounters
from .enrich import enrich_zone
from .fetcher import fetch_zone


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="bis-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show API points budget")
    sub.add_parser("discover", help="fetch+cache spec list, encounters, servers")

    fetch = sub.add_parser("fetch", help="fetch rankings for a zone")
    fetch.add_argument("zone", choices=sorted(ZONES), help="zone tag")
    fetch.add_argument(
        "--encounter", type=int, default=None, help="only this encounter id (for estimates)"
    )
    fetch.add_argument(
        "--region-only",
        action="store_true",
        help="fetch only the region-level windows (pages 1-20 per US/EU): no "
        "page-20 probe, no server descent — completes the top-2000 band",
    )
    fetch.add_argument(
        "--max-pages",
        type=int,
        default=20,
        choices=range(1, 21),
        metavar="1-20",
        help="pages per slice (100 rows each). <20 = shallow 'basic' pass, "
        "deepened for free later; 20 = full depth with server descent",
    )

    agg = sub.add_parser("aggregate", help="aggregate raw pages into per-spec distributions")
    agg.add_argument("zone", choices=sorted(ZONES) + sorted(PHASES), help="phase or zone tag")
    agg.add_argument(
        "--max-pages",
        type=int,
        default=5,
        choices=range(1, 21),
        metavar="1-20",
        help="read at most this many pages per slice (match the fetch depth)",
    )

    sub.add_parser("item-phases", help="fetch/refresh per-item release phases from wowhead")

    enrich = sub.add_parser("enrich", help="join aggregated data with cmangos item facts")
    enrich.add_argument("zone", choices=sorted(ZONES) + sorted(PHASES), help="phase or zone tag")

    args = parser.parse_args()

    if args.command == "aggregate":  # offline; needs no API client
        aggregate_zone(args.zone, max_pages=args.max_pages)
        return
    if args.command == "enrich":  # offline; needs no API client
        enrich_zone(args.zone)
        return
    if args.command == "item-phases":  # wowhead, not WCL — no client needed
        from .item_phases import build_item_phases

        build_item_phases()
        return

    client = WCLClient()

    if args.command == "status":
        print(client.points_status())
    elif args.command == "discover":
        specs = class_specs(client)
        print(f"{len(specs)} class/spec pairs:")
        for pair in specs:
            print(f"  {pair['class']} / {pair['spec']}")
        for tag, zone in ZONES.items():
            encounters = zone_encounters(client, zone["zone_id"])
            print(f"{tag}: {len(encounters)} encounters")
        servers = regions_servers(client)
        for region, slugs in servers.items():
            print(f"{region}: {len(slugs)} servers")
    elif args.command == "fetch":
        fetch_zone(
            client,
            args.zone,
            only_encounter=args.encounter,
            max_pages=args.max_pages,
            region_only=args.region_only,
        )
