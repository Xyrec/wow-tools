"""Project configuration: paths, endpoints, and the zone/partition map."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
META_DIR = DATA_DIR / "meta"
TOKEN_CACHE = DATA_DIR / ".token.json"
ENV_FILE = PROJECT_ROOT / ".env"

OAUTH_TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
CLASSIC_API_URL = "https://classic.warcraftlogs.com/api/v2/client"

# Stop fetching and sleep until reset when fewer points than this remain.
POINTS_SAFETY_MARGIN = 20.0
MAX_PAGE = 20  # Hard API cap per filter combination.
PAGE_SIZE = 100

# 2021 TBC Classic run zones (the frozen 7-partition ones) and, per raid, the
# LATEST partition before the NEXT tier released. A raid's earliest partition
# only holds the progression window (people still in last tier's gear —
# verified: zone 1011 partition 4 "P3" is Jan-Feb 2022 only); the nerf-era
# sub-partitions (P2.5, "P3.5 & P4") hold the farm-status parses that define
# phase BiS. Items from a LATER-phase raid inside a shared partition (ZA in
# "P3.5 & P4") are flagged via lootmap cross-referencing, not avoided.
# Partition indexes per zone: [1:P1, 2:P2, 3:P2.5, 4:P3, 5:"P3.5 & P4",
# 6:P5, 7:Pre-Patch]. Verified live 2026-08-15/16 (see docs/PLAN.md).
ZONES: dict[str, dict] = {
    "karazhan": {"zone_id": 1007, "partition": 1, "anniversary_phase": 1},
    "gruul-magtheridon": {"zone_id": 1008, "partition": 1, "anniversary_phase": 1},
    "ssc-tk": {"zone_id": 1010, "partition": 3, "anniversary_phase": 2},
    "bt-hyjal": {"zone_id": 1011, "partition": 5, "anniversary_phase": 3},
    "zul-aman": {"zone_id": 1012, "partition": 5, "anniversary_phase": 4},
    "sunwell": {"zone_id": 1013, "partition": 6, "anniversary_phase": 5},
}

# Anniversary phases -> the WCL zones whose raids belong to that gear era.
# Output datasets (aggregated/enriched/app) are keyed by phase, pooling all of
# the phase's zones; only phase 1 spans two WCL zones.
PHASES: dict[str, list[str]] = {
    "phase-1": ["karazhan", "gruul-magtheridon"],
    "phase-2": ["ssc-tk"],
    "phase-3": ["bt-hyjal"],
    "phase-4": ["zul-aman"],
    "phase-5": ["sunwell"],
}


def resolve_phase(tag: str) -> str:
    """Accept a phase tag or a zone tag; return the phase tag."""
    if tag in PHASES:
        return tag
    for phase_tag, zone_tags in PHASES.items():
        if tag in zone_tags:
            return phase_tag
    raise KeyError(f"unknown phase/zone tag: {tag}")


def phase_number(phase_tag: str) -> int:
    return int(phase_tag.split("-")[1])


# Specs ranked by HPS on Warcraft Logs; everything else ranks by DPS.
HEALER_SPECS = {"Restoration", "Holy", "Discipline"}

# gameData on the classic endpoint covers all classic versions; these classes
# do not exist in TBC and would only produce empty (but billed) queries.
EXCLUDED_CLASSES = {"Death Knight", "Monk"}

# Xyrec directive 2026-08-15: only US and EU data. KR/TW/CN roughly double the
# cost and describe player populations on a client/patch that never overlapped
# with the Anniversary meta.
REGIONS = ("US", "EU")


def metric_for_spec(spec_name: str) -> str:
    return "hps" if spec_name in HEALER_SPECS else "dps"


def load_env() -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE lines, # comments)."""
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env
