#!/usr/bin/env python3
"""Structural audit of a WeakAuras displays table (spec §6)."""
import json
import pathlib
import subprocess
import sys

GROUP_TYPES = {"group", "dynamicgroup"}


def audit_displays(displays: dict) -> list:
    issues = []
    uids = {}
    for key, aura in displays.items():
        aura_id = aura.get("id")
        if aura_id != key:
            issues.append(f"{key}: key/id mismatch (id={aura_id!r})")
        if not aura.get("uid"):
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
