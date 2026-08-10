"""Archetype factory invariants + the pilot parity gate."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "build"))
import archetypes  # noqa: E402
import build_group  # noqa: E402
import parity  # noqa: E402
import style as style_mod  # noqa: E402

STYLE = style_mod.load()


def test_every_archetype_positions_via_row():
    for arch in archetypes.icon_archetypes():
        base = archetypes.base_aura(STYLE, arch)
        assert base["xOffset"] == 0 and base["yOffset"] == 0, arch
        assert base["anchorPoint"] == "CENTER" and base["selfPoint"] == "CENTER", arch
        assert "scale" not in base, arch  # scale is the root group's job


def test_every_archetype_uses_row_size_and_canonical_text():
    for arch in archetypes.icon_archetypes():
        base = archetypes.base_aura(STYLE, arch)
        row = style_mod.icon_row(STYLE, archetypes.default_row(arch))
        assert (base["width"], base["height"]) == (row["width"], row["height"]), arch
        text = next(s for s in base["subRegions"] if s.get("type") == "subtext")
        assert text["text_fontSize"] == row["text_size"], arch
        assert text["text_font"] == STYLE["fonts"]["family"], arch
        border = next(s for s in base["subRegions"] if s.get("type") == "subborder")
        assert border["border_color"] == STYLE["colors"]["black"], arch


def test_archetype_alpha_base_from_style():
    for arch in archetypes.icon_archetypes():
        base = archetypes.base_aura(STYLE, arch)
        assert base["alpha"] == STYLE["alpha_rule"]["base"], arch


def test_base_auras_are_fresh_copies():
    a = archetypes.base_aura(STYLE, "rotation_icon")
    b = archetypes.base_aura(STYLE, "rotation_icon")
    a["subRegions"].append({"type": "subtext"})
    assert len(b["subRegions"]) == 3


def test_pilot_parity_against_live_snapshot():
    """The three pilot defs must reproduce their snapshot auras byte-exact."""
    pilot_ids = [
        "Shaman - Stormstrike",
        "Shaman - Nature's Swiftness",
        "Shaman - Fire Totem Missing",
    ]
    built = build_group.build("shaman", allow_missing=True)
    snapshot = json.loads(
        (ROOT / "data" / "auras" / "mine" / "xyrec-shaman-live.json").read_text())
    lines = parity.compare(built, snapshot, only=pilot_ids)
    assert not lines, "\n".join(lines)
