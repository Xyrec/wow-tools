import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from style_fields import STYLE_FIELDS, LOGIC_FIELDS
from template_extract import extract_template
from restyle import apply_template

EXEMPLAR = {
    "id": "Mine - Pretty", "uid": "MMMMMMMMMMM", "regionType": "icon",
    "width": 40, "height": 40, "zoom": 0.3, "cooldown": True, "cooldownSwipe": True,
    "anchorFrameType": "UIPARENT", "frameStrata": 1, "scale": 0.75, "alpha": 1,
    "subRegions": [{"type": "subbackground"},
                   {"type": "subtext", "text_fontSize": 14, "text_text": "%p"}],
    "triggers": {"1": {"trigger": {"type": "aura2", "auranames": ["My Spell"]}},
                 "activeTriggerMode": -10},
    "load": {"class": {"multi": {"SHAMAN": True}}},
}

DONOR = {
    "id": "Donor - Ugly", "uid": "UUUUUUUUUUU", "regionType": "icon",
    "width": 64, "height": 64, "zoom": 0, "cooldown": False,
    "desc": "from some TBC pack",
    "someUnknownField": 42,
    "triggers": {"1": {"trigger": {"type": "cooldown", "spellIds": [17364]}},
                 "activeTriggerMode": -10},
    "conditions": [{"check": {"trigger": 1}}],
    "load": {"class": {"multi": {"SHAMAN": True}}, "talent": {"multi": {"5": True}}},
}


def test_extract_template():
    tpl = extract_template(EXEMPLAR)
    assert tpl["regionType"] == "icon"
    assert tpl["width"] == 40 and tpl["cooldownSwipe"] is True
    assert "triggers" not in tpl and "id" not in tpl and "uid" not in tpl


def test_apply_template_keeps_logic_takes_style():
    tpl = extract_template(EXEMPLAR)
    out, report = apply_template(dict(DONOR), tpl)
    # style from template
    assert out["width"] == 40 and out["zoom"] == 0.3 and out["cooldown"] is True
    assert out["subRegions"] == EXEMPLAR["subRegions"]
    # logic from donor
    assert out["triggers"] == DONOR["triggers"]
    assert out["conditions"] == DONOR["conditions"]
    assert out["load"] == DONOR["load"]
    assert out["id"] == "Donor - Ugly" and out["uid"] == "UUUUUUUUUUU"
    assert out["desc"] == "from some TBC pack"
    # unknown key carried over but reported
    assert out["someUnknownField"] == 42
    assert any("someUnknownField" in line for line in report)


def test_region_type_mismatch_is_rejected():
    tpl = extract_template(EXEMPLAR)
    bar = dict(DONOR); bar["regionType"] = "aurabar"
    out, report = apply_template(bar, tpl)
    assert out == bar                      # unchanged
    assert any("regionType" in line for line in report)
