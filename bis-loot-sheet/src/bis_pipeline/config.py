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

# 2021 TBC Classic run zones (the frozen 7-partition ones) and the EARLIEST
# partition in which each raid existed. Later partitions poison the data with
# gear that was unreleased in the anniversary phase we are modeling.
# Verified live against the API on 2026-08-15 (see docs/PLAN.md).
ZONES: dict[str, dict] = {
    "karazhan": {"zone_id": 1007, "partition": 1, "anniversary_phase": 1},
    "gruul-magtheridon": {"zone_id": 1008, "partition": 1, "anniversary_phase": 1},
    "ssc-tk": {"zone_id": 1010, "partition": 2, "anniversary_phase": 2},
    "bt-hyjal": {"zone_id": 1011, "partition": 4, "anniversary_phase": 3},
    "zul-aman": {"zone_id": 1012, "partition": 5, "anniversary_phase": 4},
    "sunwell": {"zone_id": 1013, "partition": 6, "anniversary_phase": 5},
}

# Specs ranked by HPS on Warcraft Logs; everything else ranks by DPS.
HEALER_SPECS = {"Restoration", "Holy", "Discipline"}

# gameData on the classic endpoint covers all classic versions; these classes
# do not exist in TBC and would only produce empty (but billed) queries.
EXCLUDED_CLASSES = {"Death Knight", "Monk"}


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
