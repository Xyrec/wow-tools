"""Full-group parity: built shaman == live snapshot, byte-exact modulo uid.

This is the refactor's load-bearing invariant. It must stay green from the
Phase-A decompile onward; after the Phase-B cleanup land it re-pins against
the refreshed snapshot automatically (same file path).
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "build"))
import build_group  # noqa: E402
import parity  # noqa: E402

SNAPSHOT = ROOT / "data" / "auras" / "mine" / "xyrec-shaman-live.json"


def test_full_group_parity():
    built = build_group.build("shaman")
    snapshot = json.loads(SNAPSHOT.read_text())
    lines = parity.compare(built, snapshot)
    assert not lines, "parity broken:\n" + "\n".join(lines[:40])


def test_every_leaf_has_a_def():
    snapshot = json.loads(SNAPSHOT.read_text())
    built = build_group.build("shaman")
    assert len(built["c"]) == len(snapshot["c"])
