"""Cruft recognizers + repoint (tools/build/scrub.py)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "build"))
import scrub  # noqa: E402


def _aura(**kw):
    base = {"id": "X", "regionType": "icon", "triggers": {}, "load": {}}
    base.update(kw)
    return base


def test_bogus_class_multi():
    a = _aura(load={"use_class": True,
                    "class": {"single": "SHAMAN",
                              "multi": {"SHAMAN": True, "PALADIN": True, "DRUID": True}}})
    found = scrub.find_cruft(a)
    assert [(p, r) for p, _, r in found] == [("load.class.multi", "bogus-class-multi")]
    cleaned, applied = scrub.apply_scrub(a)
    assert cleaned["load"]["class"]["multi"] == {"SHAMAN": True}
    assert a["load"]["class"]["multi"]["PALADIN"] is True  # input untouched


def test_unused_load_blob_removed_only_when_flag_off():
    a = _aura(load={"use_race": False, "race": {"multi": {"Dwarf": True}},
                    "use_not_spellknown": False, "not_spellknown": 642})
    cleaned, _ = scrub.apply_scrub(a)
    assert cleaned["load"]["race"] == {"multi": []}
    assert "not_spellknown" not in cleaned["load"]
    # flag ON -> untouched
    b = _aura(load={"use_not_spellknown": True, "not_spellknown": 25547})
    cleaned_b, applied_b = scrub.apply_scrub(b)
    assert cleaned_b["load"]["not_spellknown"] == 25547 and not applied_b


def test_dead_trigger_namelist():
    a = _aura(triggers={"1": {"trigger": {"type": "spell",
                                          "auranames": ["Blood Fury"],
                                          "realSpellName": "War Stomp"}}})
    cleaned, applied = scrub.apply_scrub(a)
    assert cleaned["triggers"]["1"]["trigger"]["auranames"] == []
    assert applied == [("triggers.1.trigger.auranames", "dead-trigger-namelist")]
    # aura2 trigger actually matching by name -> kept
    b = _aura(triggers={"1": {"trigger": {"type": "aura2", "useName": True,
                                          "auranames": ["8050"]}}})
    assert not scrub.find_cruft(b)


def test_repoint_ids_scalar_list_and_drop():
    aura = {"triggers": {"1": {"trigger": {"spellName": 408510,
                                           "auranames": ["408510", "974"],
                                           "spellId": ["425336"]}}},
            "load": {"spellknown": 408510}}
    applied = scrub.repoint_ids(aura, {"408510": 24398, "425336": "drop"})
    tr = aura["triggers"]["1"]["trigger"]
    assert tr["spellName"] == 24398
    assert tr["auranames"] == ["24398", "974"]
    assert tr["spellId"] == []
    assert aura["load"]["spellknown"] == 24398
    assert ("425336", "drop") in [(str(a), b) for a, b in applied]


def test_ooc_alpha_condition_detection():
    canonical = {"changes": [{"property": "alpha", "value": 1}],
                 "check": {"trigger": -2, "variable": "OR",
                           "checks": [{"trigger": -1, "value": 1,
                                       "variable": "attackabletarget"},
                                      {"trigger": -1, "value": 1,
                                       "variable": "incombat"}]}}
    donor_variant = {"changes": [{"property": "alpha", "value": 0.49}],
                     "check": {"trigger": -1, "value": 0, "variable": "incombat"}}
    unrelated = {"changes": [{"property": "desaturate", "value": True}],
                 "check": {"trigger": 1, "value": 1, "variable": "show"}}
    assert scrub.is_ooc_alpha_condition(canonical)
    assert scrub.is_ooc_alpha_condition(donor_variant)
    assert not scrub.is_ooc_alpha_condition(unrelated)


def test_root_group_list_triggers_tolerated():
    a = _aura(regionType="group", triggers=[{"trigger": {}}])
    assert scrub.find_cruft(a) == []
