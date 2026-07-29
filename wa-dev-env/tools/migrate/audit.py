#!/usr/bin/env python3
"""Structural audit of a WeakAuras displays table (spec §6)."""
import json
import pathlib
import subprocess
import sys

GROUP_TYPES = {"group", "dynamicgroup"}

# canonical centered cooldown/timer text on Xyrec icons, read from the style
# guide. Size follows the row's icon width; %s counters may deviate
# deliberately (Personal Shield stacks).
_STYLE = json.loads((pathlib.Path(__file__).resolve().parents[2]
                     / "styles" / "xyrec.json").read_text())
CENTER_TEXT_CANON = {"text_font": _STYLE["fonts"]["family"],
                     "text_fontType": _STYLE["fonts"]["type"],
                     "text_color": _STYLE["colors"]["white"]}
CENTER_TEXT_SIZE_BY_WIDTH = {row["width"]: row["text_size"]
                             for row in _STYLE["icon_rows"].values()}
ALPHA_RULE = _STYLE["alpha_rule"]


def check_center_text(key, aura, issues):
    if aura.get("regionType") != "icon" or not key.startswith("Xyrec"):
        return
    canon = dict(CENTER_TEXT_CANON)
    size = CENTER_TEXT_SIZE_BY_WIDTH.get(aura.get("width"))
    if size:
        canon["text_fontSize"] = size
    for i, s in enumerate(aura.get("subRegions") or []):
        if (s.get("type") == "subtext" and s.get("text_text") == "%p"
                and s.get("text_selfPoint") == "AUTO" and s.get("text_visible")):
            for field, want in canon.items():
                if s.get(field) != want:
                    issues.append(f"{key}: sub.{i + 1} center text {field}="
                                  f"{s.get(field)!r} (canon: {want!r})")


def check_style_rules(key, aura, displays, issues):
    """Xyrec-group style-guide invariants beyond text canon."""
    if not key.startswith("Xyrec"):
        return
    region = aura.get("regionType")
    if region in GROUP_TYPES:
        if region == "dynamicgroup":
            for child in aura.get("controlledChildren") or []:
                ca = displays.get(child) or {}
                if ca.get("xOffset") or ca.get("yOffset"):
                    issues.append(f"{child}: nonzero offset inside dynamicgroup {key}")
        return
    if aura.get("alpha") != ALPHA_RULE["base"]:
        issues.append(f"{key}: base alpha {aura.get('alpha')!r} "
                      f"(canon: {ALPHA_RULE['base']})")
    want_checks = ALPHA_RULE["condition"]["check"]["checks"]
    for cond in aura.get("conditions") or []:
        if not isinstance(cond, dict):
            continue
        chk = cond.get("check") or {}
        if chk.get("variable") == "OR" and any(
                isinstance(ch, dict) and ch.get("property") == "alpha"
                for ch in cond.get("changes") or []):
            if all(w in (chk.get("checks") or []) for w in want_checks):
                return
    issues.append(f"{key}: missing canonical alpha-dim condition")


def audit_displays(displays: dict) -> list:
    issues = []
    uids = {}
    # built (pre-land) displays have no uids at all — that's fine; a MIX of
    # with/without uid in a live table is what indicates corruption
    any_uid = any(a.get("uid") for a in displays.values())
    for key, aura in displays.items():
        aura_id = aura.get("id")
        check_center_text(key, aura, issues)
        check_style_rules(key, aura, displays, issues)
        if aura_id != key:
            issues.append(f"{key}: key/id mismatch (id={aura_id!r})")
        if not aura.get("uid"):
            if any_uid:
                issues.append(f"{key}: missing uid")
        else:
            uids.setdefault(aura["uid"], []).append(key)
        if not aura.get("regionType"):
            issues.append(f"{key}: missing regionType")
        if "triggers" not in aura:
            issues.append(f"{key}: no triggers table")
        parent = aura.get("parent")
        if parent is not None:
            pa = displays.get(parent)
            if pa is None:
                issues.append(f"{key}: parent {parent!r} does not exist")
            elif key not in (pa.get("controlledChildren") or []):
                issues.append(f"{key}: not listed in parent {parent!r} controlledChildren")
        cc = aura.get("controlledChildren")
        if cc is not None:
            if aura.get("regionType") not in GROUP_TYPES:
                issues.append(f"{key}: has controlledChildren but regionType "
                              f"{aura.get('regionType')!r}")
            seen = set()
            for child in cc:
                if child in seen:
                    issues.append(f"{key}: duplicate controlledChildren entry {child!r}")
                seen.add(child)
                ca = displays.get(child)
                if ca is None:
                    issues.append(f"{key}: dangling controlledChildren ref {child!r}")
                elif ca.get("parent") != key:
                    issues.append(f"{key}: child {child!r} has parent "
                                  f"{ca.get('parent')!r}, expected {key!r}")
            if aura.get("regionType") == "dynamicgroup" and len(cc) == 0:
                issues.append(f"{key}: empty dynamicgroup")
    for uid, keys in uids.items():
        if len(keys) > 1:
            issues.append(f"duplicate uid {uid!r}: {', '.join(sorted(keys))}")
    return sorted(issues)


def main() -> int:
    if len(sys.argv) > 1:
        displays = json.loads(pathlib.Path(sys.argv[1]).read_text())
    else:
        repo = pathlib.Path(__file__).resolve().parents[2]
        out = subprocess.run([str(repo / "tools" / "wa"), "dump-displays"],
                             capture_output=True, text=True, check=True)
        displays = json.loads(out.stdout)
    issues = audit_displays(displays)
    for issue in issues:
        print(issue)
    print(f"{len(displays)} displays, {len(issues)} issues")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
