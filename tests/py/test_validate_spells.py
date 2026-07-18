import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from groundtruth import GroundTruth
from validate_spells import validate_payload


def make_gt(tmp_path):
    gt = tmp_path / "gt"
    (gt / "db2").mkdir(parents=True)
    (gt / "spells.json").write_text(json.dumps({
        "8050": {"name": "Flame Shock", "rank": "Rank 1"},
        "8052": {"name": "Flame Shock", "rank": "Rank 2"},
        "30455": {"name": "Ice Lance"},
    }))
    (gt / "db2" / "SpellName.csv").write_text(
        "ID,Name_lang\n8050,Flame Shock\n8052,Flame Shock\n30455,Ice Lance\n99999,Db2 Only Spell\n")
    return GroundTruth.load(gt)


def test_groundtruth_lookup(tmp_path):
    gt = make_gt(tmp_path)
    assert gt.spell_by_id(8050)["name"] == "Flame Shock"
    assert sorted(gt.ids_by_name("Flame Shock")) == [8050, 8052]
    assert gt.spell_by_id(99999)["name"] == "Db2 Only Spell"   # db2 fallback
    assert gt.source_of(8050) == "ingame" and gt.source_of(99999) == "db2"
    assert gt.spell_by_id(12345) is None


def test_validate_payload(tmp_path):
    gt = make_gt(tmp_path)
    payload = {"m": "d", "v": 2000, "d": {
        "id": "T", "regionType": "icon",
        "triggers": {"1": {"trigger": {"type": "aura2",
                                       "auranames": ["Flame Shock", "Bogus Spell"],
                                       "spellId": 8050}},
                     "2": {"trigger": {"type": "cooldown", "spellIds": [30455, 424242]}},
                     "activeTriggerMode": -10}}}
    findings = validate_payload(payload, gt)
    by = {(f["kind"], str(f["value"])): f["status"] for f in findings}
    assert by[("name", "Flame Shock")] == "ok"
    assert by[("name", "Bogus Spell")] == "unknown"
    assert by[("id", "8050")] == "ok"
    assert by[("id", "424242")] == "unknown"
    assert all(f["aura"] == "T" for f in findings)
