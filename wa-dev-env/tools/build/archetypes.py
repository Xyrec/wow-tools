"""Archetype factories: archetype x style guide -> base WA aura dicts.

An archetype's base is the CANONICAL shape of one aura family; per-aura
deviations (extra triggers, subtext variants, tocversion relics) ride in
the definition's `overrides` layer, never here. Field sets are derived
from the live shaman exemplars — key presence matters for parity (e.g.
rotation icons carry `useTooltip`, cooldown icons don't).
"""
import copy

import style as style_mod

# animation block shared by every leaf aura in the pack
_ANIMATION_NONE = {
    "finish": {"duration_type": "seconds", "easeStrength": 3, "easeType": "none", "type": "none"},
    "main": {"duration_type": "seconds", "easeStrength": 3, "easeType": "none", "type": "none"},
    "start": {"duration_type": "seconds", "easeStrength": 3, "easeType": "none", "type": "none"},
}

_INFORMATION = {"forceEvents": True, "ignoreOptionsEventErrors": True, "showNilIsFalse": True}

# shared by all icon archetypes (canonical values; presence-exact vs exemplars)
_ICON_COMMON = {
    "regionType": "icon",
    "animation": _ANIMATION_NONE,
    "adjustedMax": "",
    "adjustedMin": "",
    "anchorFrameType": "SCREEN",
    "anchorPoint": "CENTER",
    "selfPoint": "CENTER",
    "xOffset": 0,
    "yOffset": 0,
    "auto": False,
    "color": [1, 1, 1, 1],
    "cooldown": True,
    "cooldownSwipe": True,
    "cooldownTextDisabled": True,
    "desaturate": False,
    "displayIcon": "",
    "iconSource": -1,
    "frameStrata": 1,
    "icon": True,
    "internalVersion": 90,
    "progressSource": [-1, ""],
    "tocversion": 20506,
    "useAdjustededMax": False,
    "useAdjustededMin": False,
    "useCooldownModRate": True,
    "zoom": 0.3,
    "version": 15,
    "semver": "1.4.4",
    "source": "import",
    "url": "",
    "config": [],
    "authorOptions": [],
    "information": _INFORMATION,
    "actions": {"finish": [], "init": [], "start": []},
}

# archetype -> (row name, per-archetype field deltas)
_ICON_ARCHETYPES = {
    "rotation_icon": ("core", {
        "cooldownEdge": True,
        "inverse": True,
        "keepAspectRatio": True,
        "useTooltip": False,
        "actions": {"finish": [], "init": [], "start": {"do_custom": False, "do_glow": False}},
    }),
    "cooldown_icon": ("cooldowns", {
        "cooldownEdge": False,
        "inverse": False,
        "keepAspectRatio": False,
    }),
    "reminder_icon": ("reminders", {
        "anchorFrameParent": False,
        "auto": True,
        "cooldown": False,
        "cooldownEdge": False,
        "frameStrata": 3,
        "inverse": False,
        "keepAspectRatio": False,
    }),
    "groupbuff_icon": ("groupbuffs", {
        "cooldownEdge": False,
        "inverse": False,
        "keepAspectRatio": False,
    }),
}


def icon_archetypes():
    return sorted(_ICON_ARCHETYPES)


def base_aura(style, archetype):
    """The canonical aura dict for an icon archetype (no id/triggers/load)."""
    row, deltas = _ICON_ARCHETYPES[archetype]
    base = copy.deepcopy(_ICON_COMMON)
    base.update(copy.deepcopy(deltas))
    r = style_mod.icon_row(style, row)
    base["width"] = r["width"]
    base["height"] = r["height"]
    base["alpha"] = style["alpha_rule"]["base"]
    base["subRegions"] = [
        {"type": "subbackground"},
        style_mod.border_subregion(style),
        style_mod.text_subregion(style, r["text_size"]),
    ]
    return base


def default_row(archetype):
    """The row an archetype belongs to by default."""
    return _ICON_ARCHETYPES[archetype][0]
