#!/bin/bash
set -e
cd "$(dirname "$0")/.."
ADDONS="$(luajit -e 'package.path="tools/sv/?.lua;"..package.path; io.write(require("machines").addons_path)')"
DST="$ADDONS/XyrecDump"
rm -rf "$DST"
cp -R addon/XyrecDump "$DST"
echo "installed XyrecDump -> $DST"
