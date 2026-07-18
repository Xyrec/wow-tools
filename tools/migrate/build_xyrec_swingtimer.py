#!/usr/bin/env python3
"""Transplant the wago swing-sync timer (MH/OH bars + Flurry-sync spark overlay)
into the Xyrec group: its logic verbatim, our old Swing Timer [MH]'s skin & slot.

Keeps from wago: all triggers, sync/WF/imbue conditions, config + Learning Mode.
Takes from ours: size (266x7 per bar), Mana Bar anchor slot, Clean texture, blue
palette, 1px borders, spark proportions, global-alpha dimming, load, versions.
Wago's own out-of-combat styling condition is replaced by our alpha pattern.
Text overlays are hidden (not removed — sub.N condition indices must stay valid).
"""
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "swing_timer_weakaura.json"
XYREC = REPO / "data" / "auras" / "out" / "xyrec-shaman.json"
OUT = REPO / "data" / "auras" / "out" / "xyrec-swingtimer.json"

RENAME = {
    "SwingTimer": "Xyrec Shaman - Swing Timer",
    "MH": "Xyrec Shaman - Swing Timer MH",
    "OHBar": "Xyrec Shaman - Swing Timer OH",
    "OHTick": "Xyrec Shaman - Swing Timer Sync",
}

ALPHA_CONDITION = {
    "changes": [{"property": "alpha", "value": 1}],
    "check": {"trigger": -2, "variable": "OR",
              "checks": [{"trigger": -1, "value": 1, "variable": "attackabletarget"},
                         {"trigger": -1, "value": 1, "variable": "incombat"}]},
}

BAR_W, BAR_H = 266, 7
OH_Y = -(BAR_H + 2)          # OH bar 2px below MH


def is_ooc_styling_cond(c):
    check = c.get("check", {})
    return (check.get("variable") == "incombat" and check.get("value") == 0
            and any(ch.get("property") in ("alpha", "barColor") for ch in c.get("changes", [])))


def main() -> int:
    wago = json.loads(SRC.read_text())
    xy = json.loads(XYREC.read_text())
    old = next(a for a in xy["c"] if a["id"] == "Xyrec Shaman - Swing Timer [MH]")
    by_id = {a["id"]: a for a in [wago["d"]] + wago.get("c", [])}
    report = []

    style = {  # our old bar's skin
        "texture": old["texture"], "textureSource": old.get("textureSource"),
        "backgroundColor": old["backgroundColor"], "frameStrata": old["frameStrata"],
        "icon": False, "alpha": old["alpha"],
        "internalVersion": old["internalVersion"], "tocversion": old["tocversion"],
    }
    our_blue = old["barColor"]
    our_load = json.loads(json.dumps(old["load"]))

    def base_transform(a):
        a.pop("uid", None); a.pop("wagoID", None); a["url"] = ""
        a["load"] = json.loads(json.dumps(our_load))
        a["internalVersion"] = old["internalVersion"]
        a["tocversion"] = old["tocversion"]

    # root group: takes the old bar's anchor slot
    root = by_id["SwingTimer"]
    base_transform(root)
    root["id"] = RENAME["SwingTimer"]
    root["parent"] = "PLACEHOLDER-SET-AT-LAND"
    root["controlledChildren"] = [RENAME["MH"], RENAME["OHBar"], RENAME["OHTick"]]
    for k in ("anchorPoint", "selfPoint", "anchorFrameType", "anchorFrameFrame",
              "xOffset", "yOffset", "frameStrata"):
        if old.get(k) is not None:
            root[k] = old[k]
    # the old slot fit ONE bar; shift up by the OH offset so the BOTTOM bar (OH)
    # occupies the old bar's span and nothing overlaps the Mana Bar below
    root["yOffset"] = old["yOffset"] + abs(OH_Y)
    root.pop("parent")           # land --parent wires it

    def skin_bar(a, y_offset, bar_color):
        a.update(style)
        a["width"], a["height"] = BAR_W, BAR_H
        a["xOffset"], a["yOffset"] = 0, y_offset
        a["barColor"] = bar_color
        a["sparkWidth"], a["sparkHeight"] = old["sparkWidth"], old["sparkHeight"]
        a["sparkColor"] = old["sparkColor"]
        for s in a.get("subRegions", []):
            if s.get("type") == "subborder" and s.get("border_size"):
                s["border_size"] = 1
            if s.get("type") == "subtext":
                s["text_visible"] = False
        conds = [c for c in a.get("conditions", []) if not is_ooc_styling_cond(c)]
        conds.append(json.loads(json.dumps(ALPHA_CONDITION)))
        a["conditions"] = conds

    mh, ohb, oht = by_id["MH"], by_id["OHBar"], by_id["OHTick"]
    for a in (mh, ohb, oht):
        base_transform(a)
    skin_bar(mh, 0, our_blue)
    skin_bar(ohb, OH_Y, our_blue)
    # overlay: keep transparent bar + red sync spark; only resize + dim pattern
    oht["width"], oht["height"] = BAR_W, BAR_H
    oht["xOffset"], oht["yOffset"] = 0, 0
    oht["frameStrata"] = old["frameStrata"]
    oht["alpha"] = old["alpha"]
    oht["sparkHeight"] = old["sparkHeight"]      # keep wago's 2px width (sync line)
    oht["conditions"] = list(oht.get("conditions", [])) + [json.loads(json.dumps(ALPHA_CONDITION))]

    for a in (mh, ohb, oht):
        old_id = a["id"]
        a["id"] = RENAME[old_id]
        a["parent"] = RENAME["SwingTimer"]
    report.append("skinned MH/OH to 266x7 Clean/blue, 1px borders, texts hidden")
    report.append("wago OOC styling replaced with group alpha pattern on all 3 bars")

    payload = {"m": "d", "v": 2000, "s": "5.21.8", "d": root, "c": [mh, ohb, oht]}
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for line in report:
        print(line)
    print(f"4 auras -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
