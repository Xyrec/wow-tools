"""Style-guide schema sanity + pinning against the live shaman snapshot.

The guide's values are byte-exact lifts from the snapshot; these tests keep
that true (a hand-retyped color or a drifted alpha rule fails here before it
can break group parity).
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "build"))
import style as style_mod  # noqa: E402

STYLE = style_mod.load()
SNAP = json.loads((ROOT / "data" / "auras" / "mine" / "xyrec-shaman-live.json").read_text())
BY_ID = {c["id"]: c for c in SNAP["c"]}


def test_colors_are_4_float_lists():
    for name, value in STYLE["colors"].items():
        assert isinstance(value, list) and len(value) == 4, name
        assert all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in value), name


def test_icon_rows_have_sizes_and_text_sizes():
    for row in ("core", "cooldowns", "reminders", "groupbuffs"):
        r = STYLE["icon_rows"][row]
        assert r["width"] > 0 and r["height"] > 0 and r["text_size"] > 0, row


def test_alpha_rule_matches_every_snapshot_leaf():
    want = STYLE["alpha_rule"]["condition"]
    leaves = [c for c in SNAP["c"] if c.get("regionType") not in ("group", "dynamicgroup")]
    assert len(leaves) >= 30
    for aura in leaves:
        conds = [c for c in aura.get("conditions", [])
                 if isinstance(c, dict)
                 and c.get("check", {}).get("variable") == "OR"
                 and any(ch.get("property") == "alpha"
                         for ch in c.get("changes", []) if isinstance(ch, dict))]
        assert conds, f"{aura['id']}: no alpha rule"
        # the rule may carry extra OR-checks (mana bar/tick brighten rules);
        # the canonical two checks must be present verbatim
        got = conds[0]
        got_checks = got["check"]["checks"]
        for check in want["check"]["checks"]:
            assert check in got_checks, f"{aura['id']}: alpha rule drifted"
        assert got["changes"] == want["changes"], aura["id"]
        assert aura.get("alpha") == STYLE["alpha_rule"]["base"], aura["id"]


def test_row_geometry_matches_snapshot_containers():
    rows = {
        "core": "Xyrec Shaman - Core Abilities",
        "resources": "Xyrec Shaman - Resources",
        "swing": "Xyrec Shaman - Swing Timer",
        "cooldowns": "Xyrec Shaman - Cooldowns",
        "reminders": "Xyrec Shaman - Reminders",
    }
    for row, aura_id in rows.items():
        geo = STYLE["row_geometry"][row]
        aura = BY_ID[aura_id]
        for key, value in geo.items():
            assert aura.get(key) == value, f"{row}.{key}: style={value!r} snap={aura.get(key)!r}"


def test_row_sizes_match_snapshot_exemplars():
    exemplars = {
        "core": "Xyrec Shaman - Stormstrike",
        "cooldowns": "Xyrec Shaman - Shamanistic Rage",
        "reminders": "Xyrec Shaman - Drink Expiring",
    }
    for row, aura_id in exemplars.items():
        aura = BY_ID[aura_id]
        r = STYLE["icon_rows"][row]
        assert (aura["width"], aura["height"]) == (r["width"], r["height"]), row
        text = next(s for s in aura["subRegions"] if s.get("type") == "subtext")
        assert text["text_fontSize"] == r["text_size"], row
        assert text["text_font"] == STYLE["fonts"]["family"], row


def _r9(value):
    """Round floats like the parity harness — Lua serialization round-trips
    perturb the 15th digit; 9 digits is the equality contract."""
    if isinstance(value, list):
        return [_r9(v) for v in value]
    return round(value, 9) if isinstance(value, float) else value


def test_bar_skin_matches_swing_bar():
    mh = BY_ID["Xyrec Shaman - Swing Timer MH"]
    skin = STYLE["bar_skin"]
    assert mh["texture"] == skin["texture"]
    assert _r9(mh["barColor"]) == _r9(STYLE["colors"]["swing_blue"])
    border = next(s for s in mh["subRegions"] if s.get("type") == "subborder")
    for key, value in skin["border"].items():
        assert border[key] == value, key


def test_text_subregion_helper_canonical():
    sub = style_mod.text_subregion(STYLE, 18)
    assert sub["text_font"] == "PT Sans Narrow"
    assert sub["text_fontType"] == "OUTLINE"
    assert sub["text_fontSize"] == 18
    assert sub["text_selfPoint"] == "AUTO"
    # fresh copies each call
    assert style_mod.text_subregion(STYLE, 18)["text_color"] is not sub["text_color"]
