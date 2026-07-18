# End-to-end acceptance (requires the game — user-driven)

1. Codec vs the real importer:
   - `./tools/wa extract "Shaman - Stormstrike" -o tmp/ss.json`
   - `./tools/wa encode tmp/ss.json | pbcopy`
   - In-game: WeakAuras → Import → paste. MUST preview and import cleanly.
   - Delete the imported copy afterwards.
2. Real export decodes:
   - In-game: right-click any aura group → Export to string → copy.
   - `pbpaste > tmp/real.txt && ./tools/wa decode @tmp/real.txt | head`
   - MUST print JSON with the expected ids.
3. Ground truth populated:
   - In-game: `/xdump spells 1 200000` (wait for "done"), `/xdump talents`, `/reload`.
   - `./tools/wa pull-groundtruth`
   - `python3 -c "import json;d=json.load(open('data/ground-truth/spells.json'));print(len(d))"`
     MUST be > 10000.
   - Spot-check the Ice Lance lesson: search spells.json for "Ice Lance" — record the
     actual IDs in data/ground-truth/README.md.
4. Round-trip write safety (uses the live file — game CLOSED):
   - `./tools/wa backup`
   - `./tools/wa extract "Shaman - Stormstrike" -o tmp/ss.json`
   - `./tools/wa land tmp/ss.json --parent "Shaman - Core Abilities" --delete`
     (lands the identical aura back onto itself)
   - `python3 tools/migrate/audit.py` — issue count MUST NOT increase vs tmp/audit-baseline.txt
   - Launch game: aura renders as before, BugSack clean.
5. `./tests/run.sh` passes end to end.
