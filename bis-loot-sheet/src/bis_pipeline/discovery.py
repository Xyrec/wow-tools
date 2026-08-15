"""Discover and cache API-derived metadata: class/spec list, encounters, servers."""

import json
import logging
from pathlib import Path

from .client import WCLClient
from .config import META_DIR

log = logging.getLogger(__name__)


def _cached(path: Path, fetch) -> dict | list:
    if path.exists():
        return json.loads(path.read_text())
    result = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    log.info("cached %s", path.relative_to(META_DIR.parent))
    return result


def class_specs(client: WCLClient) -> list[dict]:
    """[{class: 'Shaman', spec: 'Enhancement'}, ...] for every class/spec pair."""

    def fetch() -> list[dict]:
        data = client.query("gameData { classes { name specs { name } } }")
        pairs = []
        for cls in data["gameData"]["classes"]:
            for spec in cls["specs"]:
                pairs.append({"class": cls["name"], "spec": spec["name"]})
        return pairs

    return _cached(META_DIR / "class_specs.json", fetch)


def zone_encounters(client: WCLClient, zone_id: int) -> list[dict]:
    """[{id, name}, ...] for a zone's encounters."""

    def fetch() -> list[dict]:
        data = client.query(f"worldData {{ zone(id: {zone_id}) {{ encounters {{ id name }} }} }}")
        return data["worldData"]["zone"]["encounters"]

    return _cached(META_DIR / f"encounters-{zone_id}.json", fetch)


def regions_servers(client: WCLClient) -> dict[str, list[str]]:
    """{region compact name: [server slugs]} across all regions."""

    def query_page(page: int) -> list[dict]:
        data = client.query(
            "worldData { regions { compactName "
            f"servers(limit: 100, page: {page}) {{ total data {{ slug }} }} }} }}"
        )
        return data["worldData"]["regions"]

    def fetch() -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        totals: dict[str, int] = {}
        page = 1
        while True:
            for region in query_page(page):
                name = region["compactName"]
                totals[name] = region["servers"]["total"]
                result.setdefault(name, []).extend(s["slug"] for s in region["servers"]["data"])
            if all(len(result[name]) >= totals[name] for name in totals):
                break
            page += 1
        return result

    return _cached(META_DIR / "regions_servers.json", fetch)
