"""Decompile a live group snapshot into auras/<class>/ definitions.

Inverse of build_group.compose_leaf: subtract the archetype baseline from
each leaf; logic tables (triggers/load/conditions) go into the def verbatim
(cruft included — Phase A must stay parity-exact), the remaining residue
becomes `overrides`. Leaves outside the icon archetypes become bespoke
payload passthroughs. Multiline Lua bodies are externalized to lua/.

Usage:
  python3 tools/build/decompile.py SNAPSHOT.json --class shaman
  python3 tools/build/decompile.py SNAPSHOT.json --class shaman --cruft-report
"""
import argparse
import copy
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archetypes  # noqa: E402
import compose  # noqa: E402
import scrub  # noqa: E402
import style as style_mod  # noqa: E402
from parity import normalize_aura  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]

# row container suffix -> archetype for its leaves
ROW_ARCHETYPES = {
    "Core Abilities": ("core", "rotation_icon"),
    "Cooldowns": ("cooldowns", "cooldown_icon"),
    "Reminders": ("reminders", "reminder_icon"),
    "Group Buffs": ("groupbuffs", "groupbuff_icon"),
}

# aura fields whose multiline Lua bodies get externalized
_LUA_PATHS = [
    "triggers.{n}.trigger.custom",
    "actions.init.custom",
    "actions.start.custom",
    "actions.finish.custom",
    "customText",
]


def slugify(aura_id, prefix):
    slug = aura_id.replace(prefix, "", 1).strip()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower()
    return slug


def _get_path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def externalize_lua(aura, slug, lua_dir):
    """Move multiline Lua strings out to files; return {json-path: relpath}."""
    mapping = {}
    paths = []
    for template in _LUA_PATHS:
        if "{n}" in template:
            for key in (aura.get("triggers") or {}):
                if key.isdigit():
                    paths.append(template.replace("{n}", key))
        else:
            paths.append(template)
    for dotted in paths:
        value = _get_path(aura, dotted)
        if isinstance(value, str) and "\n" in value and "function" in value:
            name = f"{slug}--{dotted.replace('.', '-')}.lua"
            (lua_dir / name).write_text(value)
            mapping[dotted] = f"lua/{name}"
            compose.set_path(aura, dotted, f"@{name}")  # placeholder, def stores map
    return mapping


def diff(base, target):
    """Override layer such that merge(base, diff) == target."""
    if isinstance(base, dict) and isinstance(target, dict):
        out = {}
        for k in target:
            if k not in base:
                out[k] = copy.deepcopy(target[k])
            elif base[k] != target[k]:
                if isinstance(base[k], dict) and isinstance(target[k], dict):
                    out[k] = diff(base[k], target[k])
                else:
                    out[k] = copy.deepcopy(target[k])
        for k in base:
            if k not in target:
                out[k] = compose.DELETE
        return out
    return copy.deepcopy(target)


def decompile_leaf(style, aura, row, archetype, prefix, lua_dir):
    target = normalize_aura(aura)
    slug = slugify(target["id"], prefix)
    alpha = style_mod.alpha_condition(style)

    if archetype == "bespoke":
        payload = copy.deepcopy(target)
        payload.pop("parent", None)
        lua_map = externalize_lua(payload, slug, lua_dir)
        # strip placeholders: build re-inlines from the map
        d = {"id": target["id"], "archetype": "bespoke", "row": row, "payload": payload}
        if lua_map:
            d["lua"] = lua_map
        return slug, d

    conds = copy.deepcopy(target.get("conditions", []))
    alpha_idx = next((i for i, c in enumerate(conds) if c == alpha), None)
    if alpha_idx is None:
        raise SystemExit(f"{target['id']}: canonical alpha condition not found — "
                         "decompile as bespoke or fix the aura")
    conds.pop(alpha_idx)
    d = {"id": target["id"], "archetype": archetype, "row": row,
         "triggers": copy.deepcopy(target["triggers"]),
         "load": copy.deepcopy(target["load"]),
         "conditions": conds}
    if alpha_idx != len(conds):
        d["conditions_alpha_index"] = alpha_idx

    base = archetypes.base_aura(style, archetype)
    fields = {"id": d["id"], "triggers": d["triggers"], "load": d["load"]}
    fc = copy.deepcopy(conds)
    fc.insert(alpha_idx, style_mod.alpha_condition(style))
    fields["conditions"] = fc
    composed = compose.merge_layers(base, fields)
    composed["parent"] = target.get("parent")
    overrides = diff(composed, target)
    for k in ("id", "parent", "triggers", "load", "conditions"):
        overrides.pop(k, None)
    lua_map = externalize_lua(d, slug, lua_dir)
    if lua_map:
        d["lua"] = lua_map
    if overrides:
        d["overrides"] = overrides
    return slug, d


def decompile(snapshot_path, class_name):
    snap = json.loads(pathlib.Path(snapshot_path).read_text())
    style = style_mod.load()
    by_id = {c["id"]: c for c in snap["c"]}
    prefix_word = class_name.capitalize()
    prefix = f"{prefix_word} - "

    class_dir = REPO / "auras" / class_name
    defs_dir = class_dir / "defs"
    lua_dir = class_dir / "lua"
    defs_dir.mkdir(parents=True, exist_ok=True)
    lua_dir.mkdir(parents=True, exist_ok=True)

    containers = {c["id"]: c for c in snap["c"]
                  if c.get("regionType") in ("group", "dynamicgroup")}
    row_of = {}
    arch_of = {}
    for cid, container in containers.items():
        suffix = cid.replace(prefix, "", 1)
        row, arch = ROW_ARCHETYPES.get(suffix, (slugify(cid, prefix), "bespoke"))
        for child in container.get("controlledChildren", []):
            if child not in containers:
                row_of[child] = row
                arch_of[child] = arch

    def strip_uid(a):
        a = copy.deepcopy(a)
        a.pop("uid", None)
        return a

    group = {
        "class": class_name,
        "wa_version": snap["s"],
        "root": strip_uid(snap["d"]),
        "containers": [strip_uid(containers[c["id"]]) for c in snap["c"]
                       if c["id"] in containers],
        "child_order": [c["id"] for c in snap["c"]],
    }
    (class_dir / "group.json").write_text(json.dumps(group, indent=2, sort_keys=True) + "\n")

    count = 0
    for aura in snap["c"]:
        if aura["id"] in containers:
            continue
        row = row_of.get(aura["id"], "loose")
        arch = arch_of.get(aura["id"], "bespoke")
        slug, d = decompile_leaf(style, aura, row, arch, prefix, lua_dir)
        (defs_dir / f"{slug}.json").write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
        count += 1
    return count


def cruft_report(snapshot_path):
    snap = json.loads(pathlib.Path(snapshot_path).read_text())
    total = 0
    for aura in [snap["d"]] + snap["c"]:
        found = scrub.find_cruft(aura)
        for path, value, rule in found:
            print(f"{aura['id']}: {path} [{rule}] = {json.dumps(value)[:100]}")
        total += len(found)
    print(f"{total} cruft entries")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--class", dest="class_name", required=True)
    ap.add_argument("--cruft-report", action="store_true")
    args = ap.parse_args()
    if args.cruft_report:
        cruft_report(args.snapshot)
        return
    n = decompile(args.snapshot, args.class_name)
    print(f"decompiled {n} leaf auras -> auras/{args.class_name}/")


if __name__ == "__main__":
    main()
