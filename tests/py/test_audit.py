import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from audit import audit_displays


def base():
    return {
        "Group": {"id": "Group", "uid": "GGGGGGGGGGG", "regionType": "group",
                  "controlledChildren": ["Child"],
                  "triggers": {"1": {"trigger": {"type": "aura2"}}, "activeTriggerMode": -10}},
        "Child": {"id": "Child", "uid": "AAAAAAAAAAA", "regionType": "icon", "parent": "Group",
                  "triggers": {"1": {"trigger": {"type": "aura2"}}, "activeTriggerMode": -10}},
    }


def test_clean_passes():
    assert audit_displays(base()) == []


def test_dangling_child():
    d = base(); d["Group"]["controlledChildren"].append("Ghost")
    assert any("Ghost" in i and "dangling" in i for i in audit_displays(d))


def test_orphan_parent_link():
    d = base(); d["Child"]["parent"] = "Nowhere"
    assert any("Nowhere" in i for i in audit_displays(d))


def test_one_way_link():
    d = base(); d["Group"]["controlledChildren"] = []      # child still points at Group
    assert any("not listed" in i for i in audit_displays(d))


def test_empty_dynamicgroup():
    d = base()
    d["Empty"] = {"id": "Empty", "uid": "EEEEEEEEEEE", "regionType": "dynamicgroup",
                  "controlledChildren": [],
                  "triggers": {"1": {"trigger": {"type": "aura2"}}, "activeTriggerMode": -10}}
    assert any("empty dynamicgroup" in i for i in audit_displays(d))


def test_missing_uid_and_dup_uid():
    d = base()
    del d["Child"]["uid"]
    issues = audit_displays(d)
    assert any("missing uid" in i for i in issues)
    d = base(); d["Child"]["uid"] = d["Group"]["uid"]
    assert any("duplicate uid" in i for i in audit_displays(d))


def test_id_key_mismatch():
    d = base(); d["Child"]["id"] = "Renamed"
    assert any("key/id mismatch" in i for i in audit_displays(d))


def test_missing_triggers():
    d = base(); del d["Child"]["triggers"]
    assert any("no triggers" in i for i in audit_displays(d))
