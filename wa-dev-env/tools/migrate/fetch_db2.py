#!/usr/bin/env python3
"""Fetch db2 CSV exports for the installed build from wago.tools.

.build.info lives at the WoW ROOT (covers all installed products); the header
line is |-separated column specs like "Version!STRING:0"; data lines are
|-separated values. We select the wow_anniversary product row explicitly —
other products (e.g. wow_classic_era) share the file.
"""
import argparse
import pathlib
import sys
import urllib.request

# .build.info lives one level above _anniversary_, per platform
_WOW_PARENTS = {
    "Linux": "/home/xyrec/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft",
    "Darwin": "/Applications/World of Warcraft",
}
BUILD_INFO = pathlib.Path(_WOW_PARENTS[__import__("platform").system()]) / ".build.info"
PRODUCT = "wow_anniversary"
OUT_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "ground-truth" / "db2"
DEFAULT_TABLES = ["SpellName", "Spell", "Talent", "TalentTab"]


def parse_build_info(text: str, product: str = PRODUCT) -> str:
    lines = [l for l in text.strip().splitlines() if l.strip()]
    header = [c.split("!")[0] for c in lines[0].split("|")]
    version_idx = header.index("Version")
    product_idx = header.index("Product")
    for line in lines[1:]:
        cols = line.split("|")
        if len(cols) > max(version_idx, product_idx) and cols[product_idx] == product:
            version = cols[version_idx]
            if version.count(".") == 3:
                return version
    raise ValueError(f"no {product} row with a Version found in .build.info")


def fetch(table: str, build: str) -> pathlib.Path:
    url = f"https://wago.tools/db2/{table}/csv?build={build}"
    out = OUT_DIR / f"{table}.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "ccwow-dev-env/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if not data or b"," not in data.split(b"\n", 1)[0]:
        raise ValueError(f"{table}: response does not look like CSV")
    out.write_bytes(data)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default=",".join(DEFAULT_TABLES))
    args = ap.parse_args()
    build = parse_build_info(BUILD_INFO.read_text())
    print(f"installed build: {build}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for table in args.tables.split(","):
        try:
            out = fetch(table, build)
            print(f"  {table}: {out} ({out.stat().st_size} bytes)")
        except Exception as exc:  # graceful per-table failure (spec §8 risk)
            failures.append(table)
            print(f"  {table}: FAILED ({exc}) — in-game dumps remain authoritative; "
                  f"retry later or try the nearest 2.5.x build on wago.tools", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
