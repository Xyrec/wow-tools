"""Style guide loading + token resolution.

The style guide (styles/xyrec.json) holds the pack's LOOK as data: fonts,
color vocabulary, per-row icon sizes and text sizes, the bar skin, the global
alpha-dim rule, and row geometry. Values are byte-exact copies from the live
snapshot — never retype them by hand; group parity depends on exactness.
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
    """A canonical centered %p subtext in the pack font at the given size."""
    f = style["fonts"]
    return {
        "type": "subtext",
        "text_text": "%p",
        "text_font": f["family"],
        "text_fontSize": size,
        "text_fontType": f["type"],
        "text_color": color(style, "white"),
        "text_shadowXOffset": f["shadow"]["x"],
        "text_shadowYOffset": f["shadow"]["y"],
        "text_selfPoint": "AUTO",
        "text_visible": True,
    }
