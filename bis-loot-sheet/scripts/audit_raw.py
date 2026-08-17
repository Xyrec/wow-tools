"""Verify raw-cache completeness for the canonical top-2000 dataset.

For every (boss, spec, region) slice of every configured zone: the slice must
either be exhausted (full population fits in <20 pages) or hold all 20
contiguous region pages. Run from the bis-loot-sheet directory:

    uv run python scripts/audit_raw.py [zone-tag ...]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bis_pipeline.config import RAW_DIR, ZONES  # noqa: E402

tags = sys.argv[1:] or sorted(ZONES)
total_checked = 0
total_issues = []
for tag in tags:
    zone = ZONES[tag]
    zone_dir = RAW_DIR / f"zone-{zone['zone_id']}"
    checked = 0
    for enc_dir in sorted(zone_dir.glob("enc-*")):
        for spec_dir in sorted((enc_dir / f"p{zone['partition']}").glob("[A-Z]*")):
            for region in ("US", "EU"):
                rd = spec_dir / region
                checked += 1
                done = rd / "_done"
                if not done.exists():
                    total_issues.append(f"{rd}: no _done marker")
                    continue
                text = done.read_text().strip()
                meta = json.loads(text) if text else {"max_pages": 20, "exhausted": False}
                pages = sorted(int(p.stem.split("-")[1]) for p in rd.glob("page-*.json"))
                if pages != list(range(1, len(pages) + 1)):
                    total_issues.append(f"{rd}: non-contiguous pages {pages}")
                elif not meta["exhausted"] and len(pages) < 20:
                    total_issues.append(f"{rd}: incomplete ({len(pages)} pages, not exhausted)")
    total_checked += checked
    print(f"{tag}: {checked} slices")

print(f"\nchecked {total_checked} slices, {len(total_issues)} issues")
for issue in total_issues[:20]:
    print(" ", issue)
sys.exit(1 if total_issues else 0)
