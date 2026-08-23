"""Style guide loading + token resolution.

The style guide (styles/xyrec.json) holds the pack's LOOK as data: fonts,
color vocabulary, per-row icon sizes and text sizes, the bar skin, the global
alpha-dim rule, and row geometry. Values are byte-exact copies from the live
snapshot - never retype them by hand; group parity depends on exactness.
"""
import copy
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
STYLE_PATH = REPO / "styles" / "xyrec.json"


def load(path=None):
    """Load the style guide. Returns a plain dict."""
    return json.loads(pathlib.Path(path or STYLE_PATH).read_text())


def color(style, name):
    """A color token as a fresh 4-float list (never a shared reference)."""
    return list(style["colors"][name])


def icon_row(style, row):
    """Icon size + center text size for a row ('core', 'cooldowns', ...)."""
    return dict(style["icon_rows"][row])


def alpha_condition(style):
    """A fresh copy of the canonical OR(attackable, incombat) -> alpha 1 rule."""
    return copy.deepcopy(style["alpha_rule"]["condition"])


def row_geometry(style, row):
    """The per-row container fields that actually vary (about six of them)."""
    return copy.deepcopy(style["row_geometry"][row])


def text_subregion(style, size):
    """The canonical centered %p subtext at the given size.

    Field set matches the live exemplars exactly (incl. the %p time-format
    block) - a built canonical text is byte-identical to a snapshot one.
    """
    f = style["fonts"]
    return {
        "type": "subtext",
        "anchorXOffset": 0,
        "anchorYOffset": 0,
        "anchor_point": "CENTER",
        "rotateText": "NONE",
        "text_automaticWidth": "Auto",
        "text_color": color(style, "white"),
        "text_fixedWidth": 64,
        "text_font": f["family"],
        "text_fontSize": size,
        "text_fontType": f["type"],
        "text_justify": "CENTER",
        "text_selfPoint": "AUTO",
        "text_shadowColor": color(style, "black"),
        "text_shadowXOffset": f["shadow"]["x"],
        "text_shadowYOffset": f["shadow"]["y"],
        "text_text": "%p",
        "text_text_format_p_format": "timed",
        "text_text_format_p_time_dynamic_threshold": 0,
        "text_text_format_p_time_format": 0,
        "text_text_format_p_time_legacy_floor": False,
        "text_text_format_p_time_mod_rate": True,
        "text_text_format_p_time_precision": 1,
        "text_visible": True,
        "text_wordWrap": "WordWrap",
    }


def border_subregion(style):
    """The canonical 1px black border subregion."""
    return {"type": "subborder", **copy.deepcopy(style["bar_skin"]["border"])}
