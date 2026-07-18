#!/usr/bin/env python3
"""Walk a WA payload for spell references and validate against ground truth."""
import json
import pathlib
import sys

from groundtruth import GroundTruth

GT_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "ground-truth"

# trigger keys whose value is a spell NAME / a spell ID / a list of either
NAME_KEYS = {"spellName", "realSpellName", "itemName"}
NAME_LIST_KEYS = {"auranames"}
ID_KEYS = {"spellId"}
ID_LIST_KEYS = {"spellIds", "auraspellids"}


def _walk(node, path, aura_id, out):
    if isinstance(node, dict):
        for key, value in node.items():
            p = f"{path}.{key}"
            if key in NAME_KEYS and isinstance(value, str) and value:
                # WA accepts spell IDs as digit-strings wherever names go
                kind = "id" if value.isdigit() else "name"
                out.append((kind, int(value) if kind == "id" else value, p, aura_id))
            elif key in NAME_LIST_KEYS and isinstance(value, (list, dict)):
                items = value if isinstance(value, list) else value.values()
                for v in items:
                    if isinstance(v, str) and v:
                        kind = "id" if v.isdigit() else "name"
                        out.append((kind, int(v) if kind == "id" else v, p, aura_id))
            elif key in ID_KEYS and isinstance(value, (int, str)) and str(value).isdigit():
                out.append(("id", int(value), p, aura_id))
            elif key in ID_LIST_KEYS and isinstance(value, (list, dict)):
                items = value if isinstance(value, list) else value.values()
                for v in items:
                    if isinstance(v, (int, str)) and str(v).isdigit():
                        out.append(("id", int(v), p, aura_id))
            else:
                _walk(value, p, aura_id, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, f"{path}[{i}]", aura_id, out)


def validate_payload(payload, gt: GroundTruth):
    auras = [payload["d"]] + list(payload.get("c") or [])
    findings = []
    for aura in auras:
        refs = []
        _walk(aura.get("triggers", {}), "triggers", aura.get("id", "?"), refs)
        for kind, value, path, aura_id in refs:
            if kind == "id":
                rec = gt.spell_by_id(value)
                status = "ok" if rec else "unknown"
                note = (f"{rec['name']} [{gt.source_of(value)}]" if rec
                        else "spell id not in ground truth")
            else:
                ids = gt.ids_by_name(value)
                status = "ok" if ids else "unknown"
                note = (f"ids: {sorted(ids)}" if ids else "spell name not in ground truth")
            findings.append({"aura": aura_id, "path": path, "kind": kind,
                             "value": value, "status": status, "note": note})
    return findings


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_spells.py <payload.json>", file=sys.stderr)
        return 2
    payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
    gt = GroundTruth.load(GT_DIR)
    findings = validate_payload(payload, gt)
    bad = 0
    for f in findings:
        mark = "OK " if f["status"] == "ok" else "?? "
        if f["status"] != "ok":
            bad += 1
        print(f'{mark} {f["aura"]}: {f["kind"]}={f["value"]!r} at {f["path"]} — {f["note"]}')
    print(f'{len(findings)} refs, {bad} unknown')
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
