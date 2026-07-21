import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from extract_custom_code import extract_snippets

DISPLAYS = {
    "A": {"id": "A", "regionType": "icon",
          "triggers": {"1": {"trigger": {"type": "custom",
                                         "custom": "function() return true end",
                                         "customDuration": "function() return 10, GetTime() end"}},
                       "activeTriggerMode": -10},
          "actions": {"init": {"custom": "aura_env.x = 1", "do_custom": True},
                      "start": {}, "finish": {}}},
    "B": {"id": "B", "regionType": "icon",
          "triggers": {"1": {"trigger": {"type": "aura2"}}, "activeTriggerMode": -10}},
}


def test_extract_snippets():
    snips = extract_snippets(DISPLAYS)
    slots = {(s["aura"], s["slot"]) for s in snips}
    assert ("A", "triggers.1.trigger.custom") in slots
    assert ("A", "triggers.1.trigger.customDuration") in slots
    assert ("A", "actions.init.custom") in slots
    assert not any(s["aura"] == "B" for s in snips)
