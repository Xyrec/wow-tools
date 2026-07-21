package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local sv = require("sv")
local safety = require("safety")
local deepeq = require("deepeq")

-- keep test backups out of the real backups/ dir (indistinguishable names);
-- os.setenv doesn't exist in Lua 5.1, so tests/run.sh exports CCWOW_BACKUP_DIR
local BDIR = "tmp/test-backups"
assert(os.getenv("CCWOW_BACKUP_DIR") == BDIR,
  "run via tests/run.sh (sets CCWOW_BACKUP_DIR=" .. BDIR .. ")")
os.execute("mkdir -p tmp " .. BDIR)
local target = "tmp/safety_target.lua"
sv.save(target, { TestDB = { a = 1 } })

-- backup creates a timestamped copy (plain prefix compare: '-' is a Lua
-- pattern quantifier, so no pattern matching against BDIR)
local bpath = safety.backup(target)
assert(bpath:sub(1, #BDIR) == BDIR, "backup not in " .. BDIR .. ": " .. tostring(bpath))
assert(io.open(bpath, "r"), "backup file missing")

-- atomic_save writes loadable content and preserves a backup of the previous state
safety.atomic_save(target, { TestDB = { a = 2 } })
assert(sv.load(target).TestDB.a == 2, "atomic_save content wrong")

-- restore brings the old state back
safety.restore(bpath, target)
assert(sv.load(target).TestDB.a == 1, "restore failed")

-- atomic_save refuses to write corrupt data (simulate: function value is unserializable)
local ok = pcall(safety.atomic_save, target, { TestDB = { f = print } })
assert(not ok, "atomic_save accepted unserializable data")
assert(sv.load(target).TestDB.a == 1, "failed save must not touch target")

-- game-running guard: does not raise when no game runs (or honors override)
assert(pcall(safety.assert_game_closed), "guard raised unexpectedly with no game running")
print("OK test_safety")
