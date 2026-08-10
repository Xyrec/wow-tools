"""Import a Sabimaru donor class pack into auras/<class>/ definitions.

Unlike the shaman decompile (parity against a live target), imports scrub
immediately and ADOPT the Xyrec style: donor visual fields are dropped, the
archetype supplies the look. Donor logic (triggers/conditions/load) is kept,
repointed through the user-reviewed spellmap.

Two modes:
  --report   analyze the donor and print proposals; writes nothing
  (apply)    consume import-manifest.json + spellmap.json, emit
             group.json / defs/ / lua/

Manifest (auras/<class>/import-manifest.json):
  { "drop": ["<donor aura id>", ...],
    "rows": {"<donor container id>": "core|cooldowns|reminders|groupbuffs"},
    "bespoke": ["<donor aura id>", ...] }      # forced passthroughs
Spellmap (auras/<class>/spellmap.json):
  { "<sod spell id>": <tbc id> | "drop", ... } # every GONE id must appear
"""
import argparse
import copy
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archetypes  # noqa: E402
import decompile  # noqa: E402
import scrub  # noqa: E402
import style as style_mod  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "migrate"))
import style_fields  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]

# per-aura fields that survive the restyle even though they look visual
# desaturate is STATE, not style: usable-gating icons rest desaturated and a
# spellUsable/insufficientResources condition clears it — dropping the base
# value makes rage/range-gated abilities look permanently castable
_SEMANTIC_KEEP = {"iconSource", "displayIcon", "icon", "desc", "desaturate"}


def donor_prefix(donor):
    """The '<Class> - ' id prefix used by the donor pack's children."""
    counts = {}
    for aura in donor["c"]:
        m = re.match(r"^([A-Za-z]+) - ", aura["id"])
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return max(counts, key=counts.get)


def collect_spell_ids(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "itemName":
                continue  # item id, not a spell — no item ground truth to check
            if k in scrub._SPELL_ID_FIELDS and isinstance(v, (int, str)) \
                    and str(v).isdigit() and int(str(v)) > 0:
                out.add(int(str(v)))
            elif k in scrub._SPELL_ID_LIST_FIELDS and isinstance(v, list):
                for item in v:
                    if str(item).isdigit() and int(str(item)) > 0:
                        out.add(int(str(item)))
            else:
                collect_spell_ids(v, out)
    elif isinstance(node, list):
        for item in node:
            collect_spell_ids(item, out)


def analyze(donor, class_name):
    """Shared analysis used by both report and apply."""
    ground = json.loads((REPO / "data" / "ground-truth" / "spells.json").read_text())
    by_id = {c["id"]: c for c in donor["c"]}
    containers = {c["id"]: c for c in donor["c"]
                  if c.get("regionType") in ("group", "dynamicgroup")}
    prefix = donor_prefix(donor)

    row_guess = {}
    for cid in containers:
        suffix = cid.replace(f"{prefix} - ", "", 1)
        for key, (row, _) in decompile.ROW_ARCHETYPES.items():
            if suffix == key:
                row_guess[cid] = row

    dead_groups = [cid for cid, c in containers.items()
                   if c.get("regionType") == "dynamicgroup"
                   and not c.get("controlledChildren")]

    unknown_spells = {}
    for aura in donor["c"]:
        ids = set()
        collect_spell_ids(aura, ids)
        gone = sorted(i for i in ids if str(i) not in ground)
        if gone:
            unknown_spells[aura["id"]] = gone

    return {
        "prefix": prefix,
        "containers": containers,
        "row_guess": row_guess,
        "dead_groups": dead_groups,
        "unknown_spells": unknown_spells,
        "by_id": by_id,
    }


def report(donor, class_name):
    info = analyze(donor, class_name)
    print(f"donor root: {donor['d']['id']}  |  children: {len(donor['c'])}")
    print(f"id prefix: {info['prefix']!r}\n")
    print("containers:")
    for cid, c in info["containers"].items():
        n = len(c.get("controlledChildren") or [])
        row = info["row_guess"].get(cid, "??? (map in manifest or drop)")
        dead = "  [EMPTY — propose drop]" if cid in info["dead_groups"] else ""
        print(f"  {cid}  ({c['regionType']}, {n} children) -> row {row}{dead}")
    loose = [a["id"] for a in donor["c"]
             if a["id"] not in info["containers"]
             and a.get("parent") == donor["d"]["id"]]
    if loose:
        print(f"\nloose top-level auras (propose bespoke or drop): {loose}")
    print(f"\nauras with spell ids NOT in TBC ground truth "
          f"({len(info['unknown_spells'])}) — every id needs a spellmap entry:")
    for aura_id, gone in sorted(info["unknown_spells"].items()):
        print(f"  {aura_id}: {gone}")
    cruft_total = sum(len(scrub.find_cruft(a)) for a in donor["c"])
    print(f"\nrecognized cruft entries (auto-scrubbed on apply): {cruft_total}")


def label_subregions(style, archetype, aura):
    """Canonical subRegions plus the donor's extra label texts (restyled).

    Labels like 'Bless'/'-RF' and unitName readouts are SEMANTIC — a blank
    reminder icon loses its meaning — so every donor subtext beyond the
    canonical %p is carried over, wearing the pack font. Returns None when
    the canonical set already covers the donor (no override needed)."""
    base = archetypes.base_aura(style, archetype)
    extras = []
    for sub in aura.get("subRegions") or []:
        if sub.get("type") != "subtext" or sub.get("text_text") == "%p":
            continue
        kept = copy.deepcopy(sub)
        kept["text_font"] = style["fonts"]["family"]
        kept["text_fontType"] = style["fonts"]["type"]
        kept["text_shadowXOffset"] = style["fonts"]["shadow"]["x"]
        kept["text_shadowYOffset"] = style["fonts"]["shadow"]["y"]
        extras.append(kept)
    if not extras:
        return None
    return base["subRegions"] + extras


def restyle_leaf(style, aura, row, archetype):
    """Strip donor styling, keep logic + semantic fields, wear the archetype."""
    conds = [c for c in (aura.get("conditions") or [])
             if not scrub.is_ooc_alpha_condition(c)]
    d = {"id": aura["id"], "archetype": archetype, "row": row,
         "triggers": aura.get("triggers"), "load": aura.get("load"),
         "conditions": conds}
    overrides = {}
    base = archetypes.base_aura(style, archetype)
    for field in _SEMANTIC_KEEP:
        if field in aura and aura[field] != base.get(field):
            overrides[field] = copy.deepcopy(aura[field])
    subs = label_subregions(style, archetype, aura)
    if subs is not None:
        overrides["subRegions"] = subs
    # code-bearing fields are LOGIC: %c closures and custom actions must
    # survive the restyle or their subtexts render blank
    for field in ("customText", "customTextUpdate"):
        if aura.get(field) and str(aura.get(field)).strip():
            overrides[field] = aura[field]
    donor_actions = aura.get("actions") or {}
    if any(isinstance(slot, dict) and (slot.get("do_custom")
                                       or str(slot.get("custom", "")).strip())
           for slot in donor_actions.values()):
        overrides["actions"] = copy.deepcopy(donor_actions)
    if overrides:
        d["overrides"] = overrides
    return d


def apply(donor, class_name):
    class_dir = REPO / "auras" / class_name
    manifest = json.loads((class_dir / "import-manifest.json").read_text())
    spellmap = json.loads((class_dir / "spellmap.json").read_text())
    info = analyze(donor, class_name)
    style = style_mod.load()

    unmapped = {aura_id: [i for i in gone if str(i) not in spellmap]
                for aura_id, gone in info["unknown_spells"].items()}
    unmapped = {k: v for k, v in unmapped.items()
                if v and k not in set(manifest.get("drop", []))}
    if unmapped:
        raise SystemExit("unmapped GONE spell ids (add to spellmap.json or drop "
                         f"the aura in the manifest): {json.dumps(unmapped, indent=1)}")

    cap = class_name.capitalize()
    def rename(aura_id):
        # Only the root group takes the Xyrec name; children keep their donor
        # ids so name references between auras (anchorFrameFrame etc.) stay valid.
        if aura_id == donor["d"]["id"]:
            return f"Xyrec - {cap}"
        return aura_id

    drop = set(manifest.get("drop", []))
    def expand(aura_id):
        drop.add(aura_id)
        for child in (info["by_id"].get(aura_id, {}).get("controlledChildren") or []):
            expand(child)
    for aura_id in list(drop):
        expand(aura_id)
    drop |= set(info["dead_groups"])

    rows = manifest.get("rows", {})
    forced_bespoke = set(manifest.get("bespoke", []))

    defs_dir = class_dir / "defs"
    lua_dir = class_dir / "lua"
    defs_dir.mkdir(parents=True, exist_ok=True)
    lua_dir.mkdir(parents=True, exist_ok=True)

    kept_children = []
    row_of = {}
    for cid, container in info["containers"].items():
        row = rows.get(cid) or info["row_guess"].get(cid)
        for child in (container.get("controlledChildren") or []):
            if row and child not in info["containers"]:
                row_of[child] = row

    stats = {"defs": 0, "bespoke": 0, "dropped": len(drop)}
    new_prefix = f"{cap} - "
    for aura in donor["c"]:
        if aura["id"] in drop:
            continue
        aura = copy.deepcopy(aura)
        scrub.repoint_ids(aura, spellmap)
        aura, _ = scrub.apply_scrub(aura)
        old_id = aura["id"]
        aura["id"] = rename(old_id)
        if aura.get("parent"):
            aura["parent"] = rename(aura["parent"])
        if aura.get("controlledChildren") is not None:
            aura["controlledChildren"] = [rename(c) for c in aura["controlledChildren"]
                                          if c not in drop]
        aura.pop("uid", None)

        if old_id in info["containers"]:
            kept_children.append(aura)
            continue

        row = row_of.get(old_id)
        archetype = None
        if row and old_id not in forced_bespoke:
            for key, (r, arch) in decompile.ROW_ARCHETYPES.items():
                if r == row:
                    archetype = arch
        slug = decompile.slugify(aura["id"], new_prefix)
        if archetype:
            d = restyle_leaf(style, aura, row, archetype)
            lua_map = decompile.externalize_lua(d, slug, lua_dir)
            if lua_map:
                d["lua"] = lua_map
            stats["defs"] += 1
        else:
            payload = copy.deepcopy(aura)
            payload.pop("parent", None)
            scrub.normalize_resource_alpha(payload, style) \
                or scrub.normalize_tick_alpha(payload, style)
            d = {"id": aura["id"], "archetype": "bespoke",
                 "row": row or "loose", "payload": payload}
            lua_map = decompile.externalize_lua(payload, slug, lua_dir)
            if lua_map:
                d["lua"] = lua_map
            stats["bespoke"] += 1
        (defs_dir / f"{slug}.json").write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
        kept_children.append(aura)

    # root + group.json: our root shape, donor membership
    root = copy.deepcopy(donor["d"])
    root.pop("uid", None)
    root["id"] = rename(donor["d"]["id"])
    root["controlledChildren"] = [rename(c) for c in root.get("controlledChildren", [])
                                  if c not in drop]
    for key, value in style["row_geometry"]["root"].items():
        root[key] = copy.deepcopy(value)

    containers_out = []
    child_order = []
    for aura in kept_children:
        child_order.append(aura["id"])
        if aura.get("regionType") in ("group", "dynamicgroup"):
            old_id = next(k for k in info["containers"] if rename(k) == aura["id"])
            row = rows.get(old_id) or info["row_guess"].get(old_id)
            if row and row in style["row_geometry"]:
                for key, value in style["row_geometry"][row].items():
                    if key != "regionType":
                        aura[key] = copy.deepcopy(value)
            containers_out.append(aura)

    group = {"class": class_name, "wa_version": donor.get("s", "5.21.8"),
             "root": root, "containers": containers_out, "child_order": child_order}
    (class_dir / "group.json").write_text(json.dumps(group, indent=2, sort_keys=True) + "\n")
    print(f"imported {stats['defs']} archetype defs + {stats['bespoke']} bespoke, "
          f"dropped {stats['dropped']} -> auras/{class_name}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("donor")
    ap.add_argument("--class", dest="class_name", required=True)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    donor = json.loads(pathlib.Path(args.donor).read_text())
    if args.report:
        report(donor, args.class_name)
    else:
        apply(donor, args.class_name)


if __name__ == "__main__":
    main()
