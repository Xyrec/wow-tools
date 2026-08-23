#!/usr/bin/env python3
"""Transplant the wago swing-sync timer into the Xyrec group as a SINGLE bar:
its logic verbatim, our old Swing Timer [MH]'s skin & exact slot.

The wago MH aura already tracks BOTH hands (t1 main / t3 off swing) and the
OHTick sync spark has its own independent swing triggers - wago's separate
OHBar readout is redundant and is dropped entirely (2026-07-22, user call).

Keeps from wago: all triggers, sync/WF/imbue conditions, config + Learning Mode
(training ticks refitted flush into the thin bar). Takes from ours: 266x7 size,
the old bar's slot above the Mana Bar, Clean texture, blue palette, 1px borders,
protruding white leading spark, global-alpha dimming, load, versions. Wago's own
out-of-combat styling condition is replaced by our alpha pattern. Text overlays
are hidden (not removed - sub.N condition indices must stay valid).
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
    "OHTick": "Xyrec Shaman - Swing Timer Sync",
}

ALPHA_CONDITION = {
    "changes": [{"property": "alpha", "value": 1}],
    "check": {"trigger": -2, "variable": "OR",
              "checks": [{"trigger": -1, "value": 1, "variable": "attackabletarget"},
                         {"trigger": -1, "value": 1, "variable": "incombat"}]},
}

BAR_W, BAR_H = 266, 7


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
    root["controlledChildren"] = [RENAME["MH"], RENAME["OHTick"]]
    for k in ("anchorPoint", "selfPoint", "anchorFrameType", "anchorFrameFrame",
              "xOffset", "yOffset", "frameStrata"):
        if old.get(k) is not None:
            root[k] = old[k]
    # single bar -> it fits the old bar's exact Sabimaru slot (above the Mana
    # Bar, below the icon row); zero the float-noise xOffset from the donor
    root["xOffset"] = 0
    root.pop("parent")           # land --parent wires it

    def skin_bar(a, y_offset, bar_color):
        a.update(style)
        a["width"], a["height"] = BAR_W, BAR_H
        a["xOffset"], a["yOffset"] = 0, y_offset
        a["barColor"] = bar_color
        a["sparkWidth"], a["sparkHeight"] = old["sparkWidth"], old["sparkHeight"]
        a["sparkColor"] = old["sparkColor"]
        old_border = next((s for s in old.get("subRegions", [])
                           if s.get("type") == "subborder"), None)
        for s in a.get("subRegions", []):
            if s.get("type") == "subborder" and old_border:
                # wago ships border_visible=false/edge "None"; adopt the old
                # bar's 1px black border wholesale (update in place - sub.N
                # condition indices must stay valid)
                for k in ("border_color", "border_edge", "border_offset",
                          "border_size", "border_visible"):
                    s[k] = json.loads(json.dumps(old_border.get(k)))
            if s.get("type") == "subtext":
                s["text_visible"] = False
            if s.get("type") == "subtick":
                # wago's training ticks were offset for a 30px bar; fit them
                # flush inside our thin bar
                s["tick_yOffset"] = 0
                s["tick_length"] = BAR_H
        conds = [c for c in a.get("conditions", []) if not is_ooc_styling_cond(c)]
        conds.append(json.loads(json.dumps(ALPHA_CONDITION)))
        a["conditions"] = conds

    mh, oht = by_id["MH"], by_id["OHTick"]
    for a in (mh, oht):
        base_transform(a)
    skin_bar(mh, 0, our_blue)
    # Sabimaru identity: the MH bar keeps the old bar's protruding white
    # leading-edge spark (wago marked the MH position by the fill edge alone)
    mh["spark"] = True
    # overlay: keep transparent bar + red sync spark; only resize + dim pattern
    oht["width"], oht["height"] = BAR_W, BAR_H
    oht["xOffset"], oht["yOffset"] = 0, 0
    oht["frameStrata"] = old["frameStrata"]
    oht["alpha"] = old["alpha"]
    oht["sparkHeight"] = BAR_H   # sync line flush INSIDE the bar (wago: 30-on-30);
                                 # keep wago's 2px spark width
    oht["conditions"] = list(oht.get("conditions", [])) + [json.loads(json.dumps(ALPHA_CONDITION))]

    for a in (mh, oht):
        old_id = a["id"]
        a["id"] = RENAME[old_id]
        a["parent"] = RENAME["SwingTimer"]
    report.append("single-bar transplant: wago OHBar dropped (MH tracks both hands)")
    report.append("skinned MH to 266x7 Clean/blue, 1px border, white spark, texts hidden")
    report.append("wago OOC styling replaced with group alpha pattern on both auras")

    payload = {"m": "d", "v": 2000, "s": "5.21.8", "d": root, "c": [mh, oht]}
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for line in report:
        print(line)
    print(f"3 auras -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
