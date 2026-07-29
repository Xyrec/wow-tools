"""Golden test: built paladin equals the checked-in payload.

Regenerate the golden deliberately when defs change. Replaced by a live
parity test after Stage-7 QA pins a snapshot. (The former importer-
determinism test was retired when def curation began — re-importing would
clobber curated definitions by design.)
"""
import json
import pathlib
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
