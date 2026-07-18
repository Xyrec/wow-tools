"""Field classification for restyling (spec §5.3).

STYLE = presentation, copied from the exemplar template.
LOGIC = behavior, kept from the donor.
Anything else: carried over from the donor and REPORTED for review.
actions/animation are STYLE by default (glow/sound styling); use
restyle.py --keep-donor-actions when a donor's actions are behavioral.
"""

LOGIC_FIELDS = [
    "id", "uid", "parent", "regionType", "triggers", "conditions", "load",
    "desc", "url", "version", "semver", "wagoID", "config", "authorOptions",
    "information", "tocversion", "internalVersion", "source",
    "iconSource", "displayIcon", "icon",  # which icon to show follows the trigger
    "adjustedMax", "adjustedMin", "useAdjustededMax", "useAdjustededMin",
]

_COMMON_STYLE = [
    "width", "height", "xOffset", "yOffset", "anchorPoint", "anchorFrameType",
    "anchorFrameFrame", "selfPoint", "frameStrata", "scale", "alpha", "color",
    "desaturate", "inverse", "subRegions", "actions", "animation",
]

STYLE_FIELDS = {
    "common": _COMMON_STYLE,
    "icon": ["zoom", "keepAspectRatio", "cooldown", "cooldownSwipe", "cooldownEdge",
             "cooldownTextDisabled", "useCooldownModRate"],
    "aurabar": ["texture", "textureSource", "barColor", "barColor2", "backgroundColor",
                "orientation", "icon_side", "icon_color", "sparkColor", "sparkTexture",
                "sparkWidth", "sparkHeight", "sparkHidden", "spark", "borderBackdrop",
                "backdropColor", "border", "borderColor", "borderEdge", "borderInset",
                "borderOffset", "borderSize", "zoom"],
    "progresstexture": ["foregroundTexture", "backgroundTexture", "foregroundColor",
                        "backgroundColor", "orientation", "compress", "blendMode",
                        "backgroundOffset", "startAngle", "endAngle", "crop_x", "crop_y",
                        "rotation", "mirror"],
    "text": ["displayText", "fixedWidth", "font", "fontSize", "outline", "justify",
             "shadowColor", "shadowXOffset", "shadowYOffset", "wordWrap",
             "automaticWidth"],
}


def style_fields_for(region_type: str) -> list:
    return STYLE_FIELDS["common"] + STYLE_FIELDS.get(region_type, [])
