#!/usr/bin/env python3
"""Diff an original (SoD/vanilla-era) aura payload against the TBC Anniversary
client: which tracked spells no longer exist / aren't player abilities (SoD
leftovers), and which of the character's TBC abilities have no aura coverage.

Classification per tracked spell (layered, client-first):
  SPELLBOOK  - in the character's spellbook dump (player has it now)
  TALENT     - granted by a talent in the class's talent tree (Talent.csv)
  DB-ONLY    - exists in the client DB but is not a player ability we can see
               (NPC spell, other class/race, or unspecced talent of another tree)
  GONE       - not in the client DB at all: removed from this game version
"""
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from damage_report import norm_triggers, active_refs

REPO = pathlib.Path(__file__).resolve().parents[2]
GT = REPO / "data" / "ground-truth"


def arr(x):
    return x if isinstance(x, list) else list(x.values())


def load_context(class_token: str, tab_ids: set):
    spells = {int(k): v["name"] for k, v in
              json.loads((GT / "spells.json").read_text()).items()}
    db2_names = {}
    with (GT / "db2" / "SpellName.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            db2_names[int(row["ID"])] = row["Name_lang"]
    book = json.loads((GT / "spellbook.json").read_text()).get(class_token, [])
    book_names = {e["name"] for e in arr(book)}
    talent_spells = {}   # name -> tab id
    with (GT / "db2" / "Talent.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            if int(row["TabID"]) in tab_ids:
                for col in ("SpellRank_0", "SpellID"):
                    sid = int(row.get(col) or 0)
                    if sid:
                        name = db2_names.get(sid) or spells.get(sid)
                        if name:
                            talent_spells[name] = int(row["TabID"])
    return spells, db2_names, book_names, talent_spells


def classify(name, book_names, talent_spells, all_names):
    if name in book_names:
        return "SPELLBOOK"
    if name in talent_spells:
        return "TALENT"
    if name in all_names:
        return "DB-ONLY"
    return "GONE"


def main() -> int:
    payload_path = sys.argv[1]
    class_token = sys.argv[2] if len(sys.argv) > 2 else "SHAMAN"
    tab_ids = {int(x) for x in (sys.argv[3].split(",") if len(sys.argv) > 3 else ["261", "262", "263"])}
    payload = json.loads(pathlib.Path(payload_path).read_text())
    spells, db2_names, book_names, talent_spells = load_context(class_token, tab_ids)
    id2name = {}
    id2name.update(db2_names)
    id2name.update(spells)          # in-game wins
    all_names = set(id2name.values())

    auras = [payload["d"]] + list(payload.get("c") or [])
    print(f"# SoD->TBC diff: {payload['d']['id']} ({len(auras)} auras) vs {class_token}\n")
    tracked_names = set()
    by_class = {}
    for aura in auras:
        for _, val in sorted(norm_triggers(aura).items()):
            refs, _ = active_refs(val["trigger"])
            for kind, value in refs:
                name = id2name.get(value) if kind == "id" else value
                label = name if name else f"id {value} (unknown)"
                cls = classify(name, book_names, talent_spells, all_names) if name else "GONE"
                tracked_names.add(name or str(value))
                by_class.setdefault(cls, set()).add(f"{label}  <- {aura['id']}")

    for cls in ("GONE", "DB-ONLY", "TALENT", "SPELLBOOK"):
        entries = sorted(by_class.get(cls, ()))
        print(f"## {cls} ({len(entries)})")
        for e in entries:
            print(f"  {e}")
        print()

    print(f"## {class_token} abilities with NO aura coverage (from spellbook dump)")
    skip = {"Attack", "Shoot", "Basic Campfire", "Block", "Dodge", "Parry", "Cultivation",
            "Find Herbs", "Alchemy", "First Aid", "Fishing", "Cooking", "Herbalism",
            "Riding", "Language", "Opening", "Closing"}
    covered = {n.lower() for n in tracked_names if n}
    book = json.loads((GT / "spellbook.json").read_text()).get(class_token, [])
    seen = set()
    for e in arr(book):
        name = e["name"]
        if name in skip or any(name.startswith(s) for s in skip) or name in seen:
            continue
        seen.add(name)
        if name.lower() not in covered:
            print(f"  {name}" + (f" ({e.get('rank')})" if e.get("rank") else ""))
    print()
    print(f"## {class_token} TALENT-granted actives with NO aura coverage")
    for name, tab in sorted(talent_spells.items()):
        if name.lower() not in covered and name not in book_names:
            print(f"  {name} [tab {tab}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
