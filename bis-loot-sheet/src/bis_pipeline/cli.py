"""CLI entry point: uv run bis-pipeline <command>."""

import argparse
import logging

from .aggregate import aggregate_zone
from .client import WCLClient
from .config import ZONES
from .discovery import class_specs, regions_servers, zone_encounters
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
        "--max-pages",
        type=int,
        default=20,
        choices=range(1, 21),
        metavar="1-20",
        help="pages per slice (100 rows each). <20 = shallow 'basic' pass, "
        "deepened for free later; 20 = full depth with server descent",
    )

    agg = sub.add_parser("aggregate", help="aggregate raw pages into per-spec distributions")
    agg.add_argument("zone", choices=sorted(ZONES), help="zone tag")
    agg.add_argument(
        "--max-pages",
        type=int,
        default=5,
        choices=range(1, 21),
        metavar="1-20",
        help="read at most this many pages per slice (match the fetch depth)",
    )

    args = parser.parse_args()

    if args.command == "aggregate":  # offline; needs no API client
        aggregate_zone(args.zone, max_pages=args.max_pages)
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
        fetch_zone(client, args.zone, only_encounter=args.encounter, max_pages=args.max_pages)
