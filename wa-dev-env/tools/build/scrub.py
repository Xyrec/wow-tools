"""Donor-residue (cruft) recognizers, shared by decompile and import_donor.

Phase A keeps cruft verbatim in defs (parity with the live snapshot);
`report()` makes it visible. Phase B applies `apply_scrub()` to the defs,
and the resulting build diff is reviewed before the one cleanup land.
New-class imports scrub immediately (no parity target exists).

Every rule returns (json_path, value, rule_name) tuples; apply order is
deterministic. Rules only ever REMOVE unused data — anything load-bearing
(use_* flag actually set) is untouched.
"""
import copy

# load keys where a use_<key> flag of false/absent makes the data dead weight;
# (key, data_keys_it_owns)
_UNUSED_LOAD_PAIRS = [
    ("race", ["race"]),
    ("not_spellknown", ["not_spellknown"]),
    ("exact_not_spellknown", ["exact_not_spellknown"]),
    ("talent", ["talent"]),
    ("spec", ["spec"]),
    ("size", ["size"]),
    ("level", ["level"]),
    ("ingroup", ["ingroup"]),
    ("encounter", ["encounter"]),
]

# trigger fields that are copy-paste residue when their use_ flag is off
_UNUSED_TRIGGER_FIELDS = ["auranames", "spellIds", "names"]


def _class_multi_cruft(aura):
    load = aura.get("load") or {}
    cls = load.get("class") or {}
    single = cls.get("single")
    multi = cls.get("multi")
    if isinstance(multi, dict) and single:
        bogus = {k: v for k, v in multi.items() if k != single}
        if bogus:
            yield "load.class.multi", bogus, "bogus-class-multi"


def _unused_load_cruft(aura):
    load = aura.get("load") or {}
    for key, owned in _UNUSED_LOAD_PAIRS:
        if not load.get(f"use_{key}"):
            for data_key in owned:
                value = load.get(data_key)
                if isinstance(value, dict):
                    non_empty = {k: v for k, v in value.items() if v not in ([], {}, None)}
                    if non_empty:
                        yield f"load.{data_key}", value, f"unused-load-{data_key}"
                elif value not in (None, "", []):
                    yield f"load.{data_key}", value, f"unused-load-{data_key}"


def _unused_trigger_cruft(aura):
    triggers = aura.get("triggers") or {}
    if not isinstance(triggers, dict):  # root groups store a vestigial list
        return
    for key, entry in triggers.items():
        if not (isinstance(entry, dict) and "trigger" in entry):
            continue
        tr = entry["trigger"]
        for field in _UNUSED_TRIGGER_FIELDS:
            value = tr.get(field)
            if not value:
                continue
            use_flag = {"auranames": "useName", "names": "useName",
                        "spellIds": "useExactSpellId"}[field]
            if tr.get("type") in ("aura2",) and tr.get(use_flag):
                continue  # genuinely used by aura matching
            if tr.get("type") not in ("aura2",):
                yield f"triggers.{key}.trigger.{field}", value, "dead-trigger-namelist"


def find_cruft(aura):
    """All recognized cruft in one aura as (json_path, value, rule) tuples."""
    out = []
    for gen in (_class_multi_cruft, _unused_load_cruft, _unused_trigger_cruft):
        out.extend(gen(aura))
    return out


# fields whose values are spell ids (repointed at donor import via spellmap)
_SPELL_ID_FIELDS = {"spellknown", "not_spellknown", "exact_not_spellknown",
                    "spellName", "itemName"}
_SPELL_ID_LIST_FIELDS = {"spellIds", "auranames", "auraspellids", "spellId"}


def repoint_ids(node, mapping, applied=None):
    """Replace SoD spell ids with TBC ids per mapping ({old: new|'drop'}).

    Handles bare ints, numeric strings, and lists of either. Entries mapped
    to 'drop' are removed from lists / left untouched otherwise (the caller
    decides what to do with un-repointable auras). Returns the applied list.
    """
    if applied is None:
        applied = []

    def convert(value):
        key = str(value)
        if key in mapping and mapping[key] != "drop":
            applied.append((value, mapping[key]))
            return type(value)(mapping[key]) if isinstance(value, str) else mapping[key]
        return value

    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k in _SPELL_ID_FIELDS and isinstance(v, (int, str)):
                node[k] = convert(v)
            elif k in _SPELL_ID_LIST_FIELDS and isinstance(v, list):
                kept = []
                for item in v:
                    if str(item) in mapping and mapping[str(item)] == "drop":
                        applied.append((item, "drop"))
                        continue
                    kept.append(convert(item))
                node[k] = kept
            else:
                repoint_ids(v, mapping, applied)
    elif isinstance(node, list):
        for item in node:
            repoint_ids(item, mapping, applied)
    return applied


def is_ooc_alpha_condition(cond):
    """Any out-of-combat alpha-styling condition (canonical or donor variant)."""
    if not isinstance(cond, dict):
        return False
    changes = cond.get("changes") or []
    touches_alpha = any(isinstance(ch, dict) and ch.get("property") == "alpha"
                        for ch in changes)
    if not touches_alpha:
        return False
    import json as _json
    check_str = _json.dumps(cond.get("check") or {})
    return "incombat" in check_str or "attackabletarget" in check_str


def apply_scrub(aura):
    """Return (cleaned copy, applied list). Only removes recognized cruft."""
    cleaned = copy.deepcopy(aura)
    applied = []
    for path, value, rule in find_cruft(aura):
        parts = path.split(".")
        cur = cleaned
        for part in parts[:-1]:
            cur = cur.get(part, {})
        last = parts[-1]
        if rule == "bogus-class-multi":
            multi = cleaned["load"]["class"]["multi"]
            for k in list(value):
                multi.pop(k, None)
        elif last in cur:
            if isinstance(cur[last], list):
                cur[last] = []
            elif isinstance(cur[last], dict):
                cur[last] = {"multi": []} if "multi" in cur[last] else {}
            else:
                del cur[last]
        applied.append((path, rule))
    return cleaned, applied
