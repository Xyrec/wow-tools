"""Deep-merge engine for aura composition.

Merge order (each layer wins over the previous):
    archetype(style)  ->  definition fields  ->  overrides  ->  quirks

Semantics:
  - dicts merge recursively
  - lists and scalars replace wholesale
  - the "__DELETE__" sentinel removes a key set by an earlier layer
  - inputs are never mutated; output contains no shared references

Definitions supply triggers/load/conditions as WHOLE values (replace, not
merge) - trigger tables are verbatim WA data, merging inside them would
invite silent half-updates.
"""
import copy

DELETE = "__DELETE__"


def merge(base, layer):
    """Return base with layer merged on top (recursive dict merge)."""
    if not isinstance(base, dict) or not isinstance(layer, dict):
        return copy.deepcopy(layer)
    out = {k: copy.deepcopy(v) for k, v in base.items()}
    for key, value in layer.items():
        if value == DELETE:
            out.pop(key, None)
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def merge_layers(base, *layers):
    """merge() folded over any number of layers (None layers are skipped)."""
    out = copy.deepcopy(base)
    for layer in layers:
        if layer:
            out = merge(out, layer)
    return out


def set_path(obj, dotted_path, value):
    """Set a value at a JSON-ish dotted path ('triggers.1.trigger.custom').

    Numeric segments index into dicts with string keys first (WA trigger
    tables use string keys "1", "2", ...) and fall back to list indices.
    Intermediate dicts are created as needed; list segments must exist.
    """
    parts = dotted_path.split(".")
    cur = obj
    for part in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur.setdefault(part, {})
    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value
