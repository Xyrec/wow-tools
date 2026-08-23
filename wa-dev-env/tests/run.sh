#!/bin/bash
set -e
cd "$(dirname "$0")/.."
LUA51="luajit"   # LuaJIT == Lua 5.1 language/API (brew's lua@5.1 was discontinued)
export CCWOW_BACKUP_DIR="tmp/test-backups"   # keep test backups out of real backups/
export CCWOW_ALLOW_RUNNING=1   # tests only write tmp/ files - safe with the game open
for f in tests/lua/test_*.lua; do "$LUA51" "$f"; done
if ls tests/py/test_*.py >/dev/null 2>&1; then uv run python3 -m pytest tests/py -q; fi
echo "ALL TESTS PASSED"
