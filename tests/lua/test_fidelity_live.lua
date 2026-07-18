package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local sv = require("sv")
local json = require("json")
local deepeq = require("deepeq")

-- 1) SavedVariables: load(save(load(live))) deep-equals load(live)
local env1 = sv.load(sv.LIVE_PATH)
assert(env1.WeakAurasSaved and env1.WeakAurasSaved.displays, "live file missing WeakAurasSaved.displays")
local n = 0; for _ in pairs(env1.WeakAurasSaved.displays) do n = n + 1 end
assert(n > 400, "expected 400+ displays, got " .. n)
sv.save("tmp/live_rewrite.lua", env1)
local env2 = sv.load("tmp/live_rewrite.lua")
local eq, path = deepeq(env1, env2)
assert(eq, "SV round-trip mismatch at " .. tostring(path))

-- 2) JSON convention proven over ALL real displays (spec §2 numeric-key risk)
local d1 = env1.WeakAurasSaved.displays
local d2 = json.from_json(json.to_json(d1))
local eq2, path2 = deepeq(d1, d2)
assert(eq2, "JSON fidelity mismatch at " .. tostring(path2))
print("OK test_fidelity_live (" .. n .. " displays)")
