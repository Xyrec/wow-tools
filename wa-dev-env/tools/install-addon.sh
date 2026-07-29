#!/bin/bash
set -e
cd "$(dirname "$0")/.."
DST="/home/xyrec/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft/_anniversary_/Interface/AddOns/XyrecDump"
rm -rf "$DST"
cp -R addon/XyrecDump "$DST"
echo "installed XyrecDump -> $DST"
