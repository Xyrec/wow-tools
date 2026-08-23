"""Bake a group scale factor into pixel values (Xyrec groups run at scale 1).

The packs were authored at root-group scale 1.5, which renders 1px borders at
1.5 physical pixels - they flicker between 1 and 2 depending on screen
position. The fix: multiply every pixel-valued field by the factor and snap
to EVEN integers (odd exact results get +1 away from zero - Xyrec's rule, so
center-anchored frames keep integer edges), then run the group at scale 1.

Border fields are deliberately EXEMPT: border_size/border_offset stay 1 -
crisp ElvUI-style hairlines are the point of the whole exercise. Ratios,
counts, times, ids and colors are not pixel values and are never touched.
"""

PIXEL_KEYS = {
    "width", "height", "xOffset", "yOffset",
    "sparkWidth", "sparkHeight", "sparkOffsetX", "sparkOffsetY",
    "fontSize", "text_fontSize", "text_fixedWidth",
    "text_anchorXOffset", "text_anchorYOffset",
    "anchorXOffset", "anchorYOffset",
    "text_shadowXOffset", "text_shadowYOffset",
    "glowLength", "glowThickness", "glowXOffset", "glowYOffset",
    "glow_length", "glow_thickness", "length", "thickness",
    "tick_length", "tick_thickness", "tick_xOffset", "tick_yOffset",
    "space", "rowSpace", "columnSpace", "stagger", "radius",
    "xOffsetRelative", "yOffsetRelative",
    "text_size",  # styles/xyrec.json icon_rows key
}

# never descend: no pixel geometry lives here, but colliding key names do
# (authorOptions "width" is option-UI columns, trigger "duration" is seconds)
EXEMPT_SUBTREES = {"triggers", "load", "actions", "authorOptions", "config",
                   "information", "animation"}


def bake(value, factor=1.5):
    """value * factor snapped to an even integer (odd exact results +1
    away from zero; fractions to the nearest even)."""
    e = value * factor
    r = round(e)
    if abs(e - r) < 1e-6:
        n = int(r)
        if n % 2:
            n += 1 if n > 0 else -1
    else:
        n = int(2 * round(e / 2))
    return n


def _is_pixel_change(change):
    prop = str(change.get("property") or "")
    return prop.rsplit(".", 1)[-1] in PIXEL_KEYS


def transform(node, factor=1.5):
    """Recursively bake pixel values in a WA data tree, in place."""
    if isinstance(node, list):
        for item in node:
            transform(item, factor)
        return node
    if not isinstance(node, dict):
        return node
    for key, value in node.items():
        if key in EXEMPT_SUBTREES:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if key in PIXEL_KEYS:
                node[key] = bake(value, factor)
            elif key == "value" and "property" in node and _is_pixel_change(node):
                # condition change like {"property": "sub.4.text_fontSize", "value": 12}
                node[key] = bake(value, factor)
        else:
            transform(value, factor)
    return node
