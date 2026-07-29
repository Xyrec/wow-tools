"""Merge-engine semantics (tools/build/compose.py)."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "build"))
import compose  # noqa: E402


def test_dicts_merge_recursively():
    base = {"a": {"x": 1, "y": 2}, "b": 1}
    out = compose.merge(base, {"a": {"y": 3, "z": 4}})
    assert out == {"a": {"x": 1, "y": 3, "z": 4}, "b": 1}
    assert base == {"a": {"x": 1, "y": 2}, "b": 1}  # input untouched


def test_lists_and_scalars_replace_wholesale():
    base = {"colors": [1, 1, 1, 1], "n": 5}
    out = compose.merge(base, {"colors": [0, 0, 0, 1], "n": 7})
    assert out == {"colors": [0, 0, 0, 1], "n": 7}


def test_delete_sentinel_removes_keys():
    out = compose.merge({"keep": 1, "drop": 2}, {"drop": compose.DELETE})
    assert out == {"keep": 1}
    # deleting a missing key is a no-op
    assert compose.merge({"a": 1}, {"b": compose.DELETE}) == {"a": 1}


def test_no_shared_references():
    base = {"sub": {"list": [1, 2]}}
    out = compose.merge(base, {})
    out["sub"]["list"].append(3)
    assert base["sub"]["list"] == [1, 2]


def test_merge_layers_order_and_none_skip():
    out = compose.merge_layers({"v": 1}, {"v": 2}, None, {"v": 3, "w": 0})
    assert out == {"v": 3, "w": 0}


def test_determinism():
    base = {"z": 1, "a": {"m": [1], "k": 2}}
    layer = {"a": {"k": 3}, "b": True}
    one = json.dumps(compose.merge(base, layer), sort_keys=True)
    two = json.dumps(compose.merge(base, layer), sort_keys=True)
    assert one == two


def test_set_path_string_keyed_trigger_tables():
    aura = {"triggers": {"1": {"trigger": {}}}}
    compose.set_path(aura, "triggers.1.trigger.custom", "function() end")
    assert aura["triggers"]["1"]["trigger"]["custom"] == "function() end"


def test_set_path_creates_intermediate_dicts():
    obj = {}
    compose.set_path(obj, "a.b.c", 1)
    assert obj == {"a": {"b": {"c": 1}}}


def test_set_path_list_index():
    obj = {"conditions": [{"check": {}}]}
    compose.set_path(obj, "conditions.0.check", {"variable": "show"})
    assert obj["conditions"][0]["check"] == {"variable": "show"}
