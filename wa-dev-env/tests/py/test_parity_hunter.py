"""Full-group parity: built hunter == live snapshot, byte-exact modulo uid.

Same contract as the shaman test - the snapshot re-pins after every
QA land + extract cycle.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "build"))
import build_group  # noqa: E402
import parity  # noqa: E402

SNAPSHOT = ROOT / "data" / "auras" / "mine" / "xyrec-hunter-live.json"


def test_full_group_parity():
    built = build_group.build("hunter")
    snapshot = json.loads(SNAPSHOT.read_text())
    lines = parity.compare(built, snapshot)
    assert not lines, "parity broken:\n" + "\n".join(lines[:40])
