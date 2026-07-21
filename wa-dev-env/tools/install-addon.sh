#!/bin/bash
set -e
cd "$(dirname "$0")/.."
DST="/Applications/World of Warcraft/_anniversary_/Interface/AddOns/XyrecDump"
rm -rf "$DST"
cp -R addon/XyrecDump "$DST"
echo "installed XyrecDump -> $DST"
