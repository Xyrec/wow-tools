"""Golden tests for the Paladin import (until a live snapshot exists).

After the Stage-7 land, replace with a parity test against
data/auras/mine/xyrec-paladin-live.json (same harness as shaman).
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "build"))
import build_group  # noqa: E402

GOLDEN = ROOT / "data" / "auras" / "out" / "xyrec-paladin.json"


def test_built_paladin_matches_golden():
    built = build_group.build("paladin")
    golden = json.loads(GOLDEN.read_text())
    assert json.dumps(built, sort_keys=True) == json.dumps(golden, sort_keys=True), \
        "built paladin drifted from golden — regenerate deliberately if intended"


def test_importer_is_deterministic(tmp_path):
    """Re-running the importer must not change the checked-in defs."""
    before = {p.name: p.read_text()
              for p in (ROOT / "auras" / "paladin" / "defs").glob("*.json")}
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build" / "import_donor.py"),
         str(ROOT / "data" / "auras" / "donors" / "sabimaru-paladin.json"),
         "--class", "paladin"],
        check=True, capture_output=True, cwd=ROOT)
    after = {p.name: p.read_text()
             for p in (ROOT / "auras" / "paladin" / "defs").glob("*.json")}
    assert before == after
