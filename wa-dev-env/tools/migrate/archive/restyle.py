#!/usr/bin/env python3
"""Apply a style template to a donor payload: donor logic + template style."""
import argparse
import json
import pathlib

from style_fields import LOGIC_FIELDS, style_fields_for


def apply_template(aura: dict, template: dict, keep_donor_actions: bool = False):
    report = []
    if aura.get("regionType") != template["regionType"]:
        report.append(f'{aura.get("id")}: regionType {aura.get("regionType")!r} != '
                      f'template {template["regionType"]!r} - left unchanged')
        return aura, report
    style = set(style_fields_for(template["regionType"]))
    if keep_donor_actions:
        style -= {"actions", "animation"}
    out = {}
    for key, value in aura.items():
        if key in style:
            continue                      # replaced by template below (or dropped)
        out[key] = value
        if key not in LOGIC_FIELDS:
            report.append(f'{aura.get("id")}: kept unclassified donor field {key!r} - review')
    for key in style:
        if key in template:
            out[key] = template[key]
    donor_sub = aura.get("subRegions") or []
    if any("%c" in str(s.get("text_text", "")) for s in donor_sub if isinstance(s, dict)):
        report.append(f'{aura.get("id")}: donor had custom-text (%c) subregions replaced '
                      f'by template - port the custom text manually if needed')
    return out, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("payload")
    ap.add_argument("--template", required=True)
    ap.add_argument("--keep-donor-actions", action="store_true")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    payload = json.loads(pathlib.Path(args.payload).read_text())
    template = json.loads(pathlib.Path(args.template).read_text())
    auras = [payload["d"]] + list(payload.get("c") or [])
    full_report = []
    for i, aura in enumerate(auras):
        new, report = apply_template(aura, template, args.keep_donor_actions)
        full_report.extend(report)
        if i == 0:
            payload["d"] = new
        else:
            payload["c"][i - 1] = new
    pathlib.Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for line in full_report:
        print("NOTE:", line)
    print(f"restyled {len(auras)} aura(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
