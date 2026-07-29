"""Parity harness: compare a built payload against a live snapshot.

Normalization: strip `uid` everywhere, round floats to 9 places, sorted-key
JSON. Comparison covers the root aura `d` and the child list `c` (order
significant). Failures print per-aura JSON-pointer diffs.

Usage:
  python3 tools/build/parity.py BUILT.json SNAPSHOT.json [--only "<aura id>"]...
  python3 tools/build/parity.py A.json B.json --diff-payloads   # same engine,
      # used for the quirked-vs-clean review in Phase B (prints diffs, exit 0)
"""
import argparse
import json
import pathlib
import sys


def normalize_aura(aura):
    def walk(node):
        if isinstance(node, dict):
            out = {k: walk(v) for k, v in sorted(node.items()) if k != "uid"}
            # Lua has one empty table; the codec writes it as [] while
            # Python-authored defs may say {} — identical to WeakAuras
            return out if out else []
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, float):
            return round(node, 9)
        return node
    return walk(aura)


def diff_paths(a, b, path=""):
    """Yield (json-pointer, a-value, b-value) for every difference."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            p = f"{path}/{key}"
            if key not in a:
                yield p, "<missing>", b[key]
            elif key not in b:
                yield p, a[key], "<missing>"
            else:
                yield from diff_paths(a[key], b[key], p)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{path}/#len", len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diff_paths(x, y, f"{path}/{i}")
    elif a != b:
        yield path, a, b


def compare(built, snapshot, only=None, label_a="built", label_b="snapshot"):
    """Return a list of human-readable difference lines."""
    lines = []
    a_map = {c["id"]: normalize_aura(c) for c in built.get("c", [])}
    b_map = {c["id"]: normalize_aura(c) for c in snapshot.get("c", [])}
    a_map[built["d"]["id"]] = normalize_aura(built["d"])
    b_map[snapshot["d"]["id"]] = normalize_aura(snapshot["d"])

    if only:
        ids = list(only)
    else:
        ids = sorted(set(a_map) | set(b_map))
        a_order = [c["id"] for c in built.get("c", [])]
        b_order = [c["id"] for c in snapshot.get("c", [])]
        if a_order != b_order:
            lines.append(f"child order differs:\n  {label_a}: {a_order}\n  {label_b}: {b_order}")

    for aura_id in ids:
        if aura_id not in a_map:
            lines.append(f"{aura_id}: missing from {label_a}")
            continue
        if aura_id not in b_map:
            lines.append(f"{aura_id}: missing from {label_b}")
            continue
        for pointer, va, vb in diff_paths(a_map[aura_id], b_map[aura_id]):
            sa, sb = json.dumps(va, sort_keys=True), json.dumps(vb, sort_keys=True)
            lines.append(f"{aura_id}: {pointer} {label_a}={sa[:120]} {label_b}={sb[:120]}")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("built")
    ap.add_argument("snapshot")
    ap.add_argument("--only", action="append", default=None,
                    help="restrict comparison to these aura ids (repeatable)")
    ap.add_argument("--diff-payloads", action="store_true",
                    help="review mode: print diffs but always exit 0")
    args = ap.parse_args()

    built = json.loads(pathlib.Path(args.built).read_text())
    snapshot = json.loads(pathlib.Path(args.snapshot).read_text())
    labels = ("A", "B") if args.diff_payloads else ("built", "snapshot")
    lines = compare(built, snapshot, only=args.only, label_a=labels[0], label_b=labels[1])
    for line in lines:
        print(line)
    if args.diff_payloads:
        print(f"{len(lines)} difference(s)")
        return 0
    if lines:
        print(f"PARITY FAILED: {len(lines)} difference(s)")
        return 1
    print("PARITY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
