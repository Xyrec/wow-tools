"""Compare wowtbc.gg phase-3 BiS lists against our per-band distributions."""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# usage: compare_wowtbc.py [our-phase-tag] [wowtbc-phase-key]
# wowtbc phase keys (dropdown order): phase-0=Pre-Raid, 1=T4, 2=T5, 3=T6, 4=ZA, 5=SWP
# NOTE their keys are gear tiers, ours are anniversary phases: our phase-2 = their
# phase-2 (T5), our phase-3 = their phase-3 (T6), our phase-1 = their phase-1 (T4).
ZONE = sys.argv[1] if len(sys.argv) > 1 else "phase-3"
WOWTBC_PHASE = sys.argv[2] if len(sys.argv) > 2 else "phase-3"

ROOT = Path(__file__).resolve().parents[2]
ENRICHED = json.loads((ROOT / f"bis-loot-sheet/data/enriched/{ZONE}.json").read_text())

SPEC_MAP = {
    "affliction-warlock": "Warlock-Affliction", "arcane-mage": "Mage-Arcane",
    "arms-warrior": "Warrior-Arms", "assassination-rogue": "Rogue-Assassination",
    "balance-druid": "Druid-Balance", "bm-hunter": "Hunter-Beast Mastery",
    "combat-rogue": "Rogue-Combat", "demo-warlock": "Warlock-Demonology",
    "destro-warlock": "Warlock-Destruction", "elemental-shaman": "Shaman-Elemental",
    "enhancement-shaman": "Shaman-Enhancement", "feral-dps-druid": "Druid-Feral",
    "feral-tank-druid": "Druid-Guardian", "fire-mage": "Mage-Fire",
    "frost-mage": "Mage-Frost", "fury-warrior": "Warrior-Fury",
    "holy-paladin": "Paladin-Holy", "holy-priest": "Priest-Holy",
    "marks-hunter": "Hunter-Marksmanship", "prot-paladin": "Paladin-Protection",
    "prot-warrior": "Warrior-Protection", "resto-druid": "Druid-Restoration",
    "resto-shaman": "Shaman-Restoration", "ret-paladin": "Paladin-Retribution",
    "shadow-priest": "Priest-Shadow", "subtlety-rogue": "Rogue-Subtlety",
    "survival-hunter": "Hunter-Survival",
}

MERGED_WEAPONS = ("two_hand", "main_hand", "off_hand")
SLOT_MAP = {
    "head": ("head",), "chest": ("chest",), "legs": ("legs",), "waist": ("waist",),
    "shoulders": ("shoulder",), "hands": ("hands",), "feet": ("feet",),
    "neck": ("neck",), "wrists": ("wrist",), "back": ("back",),
    "rings": ("ring",), "trinkets": ("trinket",),
    "weapons": MERGED_WEAPONS, "offhands": ("off_hand",), "shields-offhands": ("off_hand",),
    "totems": ("ranged",), "idols": ("ranged",), "librams": ("ranged",),
    "ranged": ("ranged",), "relics": ("ranged",),
}
MULTI = {"rings", "trinkets", "weapons"}  # two equip slots -> wider windows
BIS_TIE_PP = 5.0
FLOOR = 2.0

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
name_to_id = {}
for iid, f in ENRICHED["items"].items():
    name_to_id.setdefault(norm(f["name"]), iid)
    if f.get("wclName"):
        name_to_id.setdefault(norm(f["wclName"]), iid)


def split_two_hand(entries):
    th, oh = [], []
    for e in entries:
        (th if ENRICHED["items"][str(e["id"])]["slot"] == "two_hand" else oh).append(e)
    return th, oh


def band_entries(spec_key, band, our_slots):
    bd = ENRICHED["specs"][spec_key]["bands"][band]
    if our_slots == MERGED_WEAPONS:
        merged = list(bd["slots"].get("main_hand", [])) + [
            e for e in bd["slots"].get("off_hand", [])
            if e["id"] not in {x["id"] for x in bd["slots"].get("main_hand", [])}
        ]
        return sorted(merged, key=lambda e: -e["pct"])
    out = []
    for s in our_slots:
        out.extend(bd["slots"].get(s, []))
    return sorted(out, key=lambda e: -e["pct"])


results = {b: defaultdict(lambda: [0, 0, 0]) for b in ("top2000", "top10", "mid50", "all")}  # strict, loose, n
absent = []

for dir_name, spec_key in SPEC_MAP.items():
    data = json.loads((ROOT / "output" / dir_name / "wtbc_bis_gear.json").read_text())
    p3 = data["phases"].get(WOWTBC_PHASE, {})
    if spec_key not in ENRICHED["specs"]:
        continue
    for wslot, entries in p3.items():
        our_slots = SLOT_MAP.get(wslot)
        if not our_slots:
            continue
        bis_items = [e["name"] for e in entries if e["rank"] == "BiS"]
        for wname in bis_items:
            # Scraper artifacts: "(OH)"/"(MH)" suffixes and empty rows.
            wname = re.sub(r"\s*\((?:OH|MH)\)\s*$", "", wname).strip()
            if not wname:
                continue
            iid = name_to_id.get(norm(wname))
            if iid is None:
                absent.append((spec_key, wslot, wname))
                continue
            for band in results:
                ours = [e for e in band_entries(spec_key, band, our_slots) if e["pct"] >= FLOOR]
                ids = [str(e["id"]) for e in ours]
                strict_n = 2 if wslot in MULTI else 1
                loose_n = 4 if wslot in MULTI else 3
                # strict: inside the co-BiS set (tie window off the top entry),
                # allowing the natural width of two-slot categories
                co_bis = [
                    str(e["id"]) for e in ours if ours and ours[0]["pct"] - e["pct"] <= BIS_TIE_PP
                ][: max(strict_n, 2)]
                s = 1 if iid in co_bis or iid in ids[:strict_n] else 0
                lo = 1 if iid in ids[:loose_n] else 0
                r = results[band][spec_key]
                r[0] += s
                r[1] += lo
                r[2] += 1

print(f"{'band':6s} {'strict':>8s} {'loose':>8s}   (n = wowtbc P3 BiS items resolvable in our data)")
for band, per_spec in results.items():
    s = sum(v[0] for v in per_spec.values())
    lo = sum(v[1] for v in per_spec.values())
    n = sum(v[2] for v in per_spec.values())
    print(f"{band:6s} {100 * s / n:7.1f}% {100 * lo / n:7.1f}%   n={n}")

print(f"\nunresolvable wowtbc BiS names (nobody wears them >= floor): {len(absent)}")
for a in absent[:10]:
    print("  ", a)

print("\nworst specs on top10 strict:")
ranked = sorted(results["top10"].items(), key=lambda kv: kv[1][0] / max(1, kv[1][2]))
for spec_key, (s, lo, n) in ranked[:5]:
    print(f"  {spec_key:24s} {100 * s / n:5.1f}% strict ({s}/{n})")
