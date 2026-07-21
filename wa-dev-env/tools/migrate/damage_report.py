#!/usr/bin/env python3
"""Per-aura damage report, ACTIVITY-AWARE: only fields the trigger's type
actually uses are treated as live; everything else is residue (WA keeps stale
fields when the author switches trigger type — harmless at runtime).
Read-only analysis for review before migration work."""
import json
import pathlib
import sys

from groundtruth import GroundTruth

GT_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "ground-truth"


def norm_triggers(aura):
    trigs = aura.get("triggers", {})
    if isinstance(trigs, list):
        return {str(i + 1): v for i, v in enumerate(trigs)}
    return {str(k): v for k, v in trigs.items() if isinstance(v, dict) and "trigger" in v}


def active_refs(tr: dict):
    """Return (refs, note): refs = list of (kind, value) live spell references."""
    ttype = tr.get("type")
    refs = []
    if ttype in ("aura", "aura2"):
        for v in (tr.get("auranames") or []):
            if isinstance(v, str) and v:
                refs.append(("id", int(v)) if v.isdigit() else ("name", v))
        for v in (tr.get("auraspellids") or []):
            if isinstance(v, (int, str)) and str(v).isdigit():
                refs.append(("id", int(v)))
        return refs, None
    if ttype == "spell":
        sn = tr.get("spellName")
        if tr.get("use_spellName") and sn is not None:
            refs.append(("id", int(sn)) if str(sn).isdigit() else ("name", str(sn)))
        return refs, None
    if ttype == "item":
        return refs, f"item trigger ({tr.get('event')}); spell fields are residue"
    if ttype == "custom":
        return refs, "custom code trigger — lint via extract_custom_code"
    if ttype == "unit":
        return refs, None
    return refs, f"unhandled trigger type {ttype!r} — review manually"


def load_summary(aura):
    load = aura.get("load", {})
    bits = []
    if load.get("use_class") and load.get("class"):
        c = load["class"]
        bits.append("class=" + str(c.get("single") or ",".join((c.get("multi") or {}).keys())))
    for talent_key in ("talent", "talent2", "talent3"):
        if load.get("use_" + talent_key) is not None and load.get(talent_key):
            bits.append(f"{talent_key}={json.dumps(load[talent_key])}")
    if load.get("use_never"):
        bits.append("NEVER LOADS")
    if load.get("use_spellknown") and load.get("spellknown"):
        bits.append(f"spellknown={load['spellknown']}")
    return bits


def main() -> int:
    payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
    gt = GroundTruth.load(GT_DIR)
    auras = [payload["d"]] + list(payload.get("c") or [])
    problems = 0
    print(f"# Damage report: {payload['d']['id']} ({len(auras)} auras)\n")
    for aura in auras:
        aura_id = aura.get("id", "?")
        lines = []
        for key, val in sorted(norm_triggers(aura).items()):
            tr = val["trigger"]
            refs, note = active_refs(tr)
            head = f"  t{key} [{tr.get('type')}/{tr.get('event') or tr.get('names') or ''}]"
            if note:
                lines.append(f"{head}: {note}")
            for kind, value in refs:
                if kind == "id":
                    rec = gt.spell_by_id(value)
                    if rec:
                        lines.append(f"{head}: id {value} = {rec['name']} [{gt.source_of(value)}]")
                    else:
                        problems += 1
                        lines.append(f"{head}: id {value} !! NOT IN GROUND TRUTH")
                else:
                    ids = gt.ids_by_name(value)
                    if ids:
                        lines.append(f"{head}: name {value!r} (ids {sorted(ids)[:6]}{'...' if len(ids) > 6 else ''})")
                    else:
                        problems += 1
                        lines.append(f"{head}: name {value!r} !! NOT IN GROUND TRUTH")
        print(f"## {aura_id} ({aura.get('regionType')})")
        for bit in load_summary(aura):
            print(f"  load: {bit}")
        print("\n".join(lines))
        print()
    print(f"TOTAL live-ref problems: {problems}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
