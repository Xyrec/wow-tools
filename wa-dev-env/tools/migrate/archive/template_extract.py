#!/usr/bin/env python3
"""Extract a style template from an exemplar aura (spec §5: style is data)."""
import argparse
import json
import pathlib

from style_fields import style_fields_for


def extract_template(aura: dict) -> dict:
    tpl = {"regionType": aura["regionType"]}
    for field in style_fields_for(aura["regionType"]):
        if field in aura:
            tpl[field] = aura[field]
    return tpl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("payload", help="payload JSON from `wa extract` (uses .d)")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.payload).read_text())
    aura = data["d"] if "d" in data else data
    tpl = extract_template(aura)
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(tpl, indent=2, sort_keys=True) + "\n")
    print(f"template ({tpl['regionType']}, {len(tpl) - 1} fields) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
