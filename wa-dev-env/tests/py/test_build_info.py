import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from fetch_db2 import parse_build_info

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "build.info"


def test_parse_build_info_selects_anniversary_product():
    version = parse_build_info(FIXTURE.read_text())
    parts = version.split(".")
    assert len(parts) == 4, f"expected a.b.c.build, got {version}"
    # the fixture also contains wow_classic_era 1.15.x - we must NOT pick that
    assert parts[0] == "2" and parts[1] == "5", f"expected 2.5.x (wow_anniversary), got {version}"
    assert parts[3].isdigit() and int(parts[3]) > 60000
