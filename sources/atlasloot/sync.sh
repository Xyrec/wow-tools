#!/usr/bin/env bash
# Syncs AtlasLoot addon folders from the WoW install into this directory.
# Run this after updating the AtlasLoot addon to refresh source data.
#
# Usage:
#   ./sources/atlasloot/sync.sh
#   ./sources/atlasloot/sync.sh /path/to/wow/Interface/AddOns

set -euo pipefail

DEFAULT_ADDONS_DIR="F:/Program Files (x86)/World of Warcraft/_anniversary_/Interface/AddOns"
ADDONS_DIR="${1:-$DEFAULT_ADDONS_DIR}"
DEST_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$ADDONS_DIR" ]; then
    echo "Error: AddOns directory not found: $ADDONS_DIR"
    echo "Usage: $0 [/path/to/wow/Interface/AddOns]"
    exit 1
fi

# Copy all AtlasLoot folders (exclude Options — UI-only, no data)
copied=0
for dir in "$ADDONS_DIR"/AtlasLootClassic*/; do
    name=$(basename "$dir")
    if [ "$name" = "AtlasLootClassic_Options" ]; then
        continue
    fi
    echo "Syncing $name..."
    rm -rf "$DEST_DIR/$name"
    cp -r "$dir" "$DEST_DIR/$name"
    copied=$((copied + 1))
done

echo "Done — synced $copied AtlasLoot folders to $DEST_DIR"
