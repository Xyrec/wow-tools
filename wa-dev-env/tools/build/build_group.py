"""Build a full WeakAuras payload from auras/<class>/ definitions.

Composition per leaf (see compose.py):
    archetype(style) -> def fields -> def.overrides -> quirks[id]
Bespoke defs skip the archetype: their `payload` is the base. Lua bodies
referenced by `lua: {json-path: file}` are re-inlined from auras/<class>/lua/.

The global alpha-dim condition is injected from the style guide at
`conditions_alpha_index` (default: appended last).

Usage:
  python3 tools/build/build_group.py <class> -o OUT.json [--allow-missing]
"""
import argparse
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archetypes  # noqa: E402
import compose  # noqa: E402
import style as style_mod  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]

DEF_KEYS = {"id", "archetype", "row", "triggers", "load", "conditions",
            "conditions_alpha_index", "lua", "overrides", "payload"}


def load_defs(class_dir):
    defs = {}
    sources = {}
    for path in sorted((class_dir / "defs").glob("*.json")):
        d = json.loads(path.read_text())
        unknown = set(d) - DEF_KEYS
        if unknown:
            raise SystemExit(f"{path.name}: unknown def keys {sorted(unknown)}")
        if d["id"] in defs:
            raise SystemExit(f"duplicate def id {d['id']!r}: "
                             f"{sources[d['id']]} and {path.name}")
        defs[d["id"]] = d
        sources[d["id"]] = path.name
    return defs


def compose_leaf(style, definition, quirks, class_dir, parent_id):
    if definition["archetype"] == "bespoke":
        aura = copy.deepcopy(definition["payload"])
    else:
        base = archetypes.base_aura(style, definition["archetype"])
        fields = {"id": definition["id"]}
        for key in ("triggers", "load"):
            if key in definition:
                fields[key] = definition[key]
        if "conditions" in definition:
            conds = copy.deepcopy(definition["conditions"])
            idx = definition.get("conditions_alpha_index", len(conds))
            conds.insert(idx, style_mod.alpha_condition(style))
            fields["conditions"] = conds
        aura = compose.merge_layers(base, fields, definition.get("overrides"),
                                    quirks.get(definition["id"]))
    aura["id"] = definition["id"]
    aura["parent"] = parent_id
    for dotted_path, rel in (definition.get("lua") or {}).items():
        body = (class_dir / rel).read_text()
        compose.set_path(aura, dotted_path, body)
    return aura


def build(class_name, allow_missing=False):
    class_dir = REPO / "auras" / class_name
    group = json.loads((class_dir / "group.json").read_text())
    style = style_mod.load()
    quirks_path = class_dir / "quirks.json"
    quirks = json.loads(quirks_path.read_text()) if quirks_path.exists() else {}
    defs = load_defs(class_dir)

    containers = {c["id"]: copy.deepcopy(c) for c in group["containers"]}
    parent_of = {}
    for cid, container in containers.items():
        for child in container.get("controlledChildren", []):
            parent_of[child] = cid
    root = copy.deepcopy(group["root"])
    for child in root.get("controlledChildren", []):
        parent_of[child] = root["id"]

    children = []
    missing = []
    for aura_id in group["child_order"]:
        if aura_id in containers:
            children.append(containers[aura_id])
        elif aura_id in defs:
            children.append(compose_leaf(style, defs[aura_id], quirks,
                                         class_dir, parent_of.get(aura_id)))
        else:
            missing.append(aura_id)
    if missing and not allow_missing:
        raise SystemExit(f"no def for: {missing} (use --allow-missing for pilots)")
    if missing:
        print(f"note: skipped {len(missing)} aura(s) without defs", file=sys.stderr)
        # keep container membership consistent with what we actually emit
        emitted = {c["id"] for c in children} | {root["id"]}
        for container in [root] + children:
            cc = container.get("controlledChildren")
            if cc:
                container["controlledChildren"] = [c for c in cc if c in emitted or c not in missing]

    extra = sorted(set(defs) - set(group["child_order"]))
    if extra:
        raise SystemExit(f"defs not listed in child_order: {extra}")

    return {"m": "d", "v": 2000, "s": group["wa_version"], "d": root, "c": children}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("class_name")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--allow-missing", action="store_true")
    ap.add_argument("--displays", action="store_true",
                    help="emit an {id: aura} displays map (audit / luacheck input) "
                         "instead of a landable payload")
    args = ap.parse_args()
    payload = build(args.class_name, allow_missing=args.allow_missing)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.displays:
        displays = {a["id"]: a for a in [payload["d"]] + payload["c"]}
        out.write_text(json.dumps(displays, indent=2, sort_keys=True) + "\n")
        print(f"{len(displays)} displays -> {out}")
    else:
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(f"{len(payload['c']) + 1} auras -> {out}")


if __name__ == "__main__":
    main()
