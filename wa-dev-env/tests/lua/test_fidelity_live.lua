package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local sv = require("sv")
local json = require("json")
local deepeq = require("deepeq")

-- 1) SavedVariables: load(save(load(live))) deep-equals load(live)
local env1 = sv.load(sv.LIVE_PATH)
assert(env1.WeakAurasSaved and env1.WeakAurasSaved.displays, "live file missing WeakAurasSaved.displays")
-- floor: the two Xyrec groups + the disabled ZulgAuras trio (Sabimaru packs
-- were purged 2026-07-29; round-trip fidelity below is the real assertion)
local n = 0; for _ in pairs(env1.WeakAurasSaved.displays) do n = n + 1 end
assert(n > 50, "expected 50+ displays, got " .. n)
assert(env1.WeakAurasSaved.displays["Xyrec - Shaman"], "Xyrec - Shaman missing")
assert(env1.WeakAurasSaved.displays["Xyrec - Paladin"], "Xyrec - Paladin missing")
sv.save("tmp/live_rewrite.lua", env1)
local env2 = sv.load("tmp/live_rewrite.lua")
local eq, path = deepeq(env1, env2)
assert(eq, "SV round-trip mismatch at " .. tostring(path))

-- 2) JSON convention proven over OUR displays (spec §2 numeric-key risk).
-- Scoped to Xyrec trees: decode coerces digit object keys to numbers, which
-- is deliberately lossy for foreign auras that use digit STRING keys (e.g.
-- Fojji's itemTypeName.multi["1030"]). Harmless in WA (multiselect keys only
-- feed string.format) and foreign auras never travel our JSON path - full-SV
-- writes go through the Lua serializer, which preserves them byte-exact.
local d1 = {}
local function claim(id)
  local a = env1.WeakAurasSaved.displays[id]
  if not a then return end
  d1[id] = a
  for _, child in ipairs(a.controlledChildren or {}) do claim(child) end
end
for id, _ in pairs(env1.WeakAurasSaved.displays) do
  if id:sub(1, 8) == "Xyrec - " then claim(id) end
end
local n2 = 0; for _ in pairs(d1) do n2 = n2 + 1 end
assert(n2 > 50, "expected 50+ Xyrec displays, got " .. n2)
local d2 = json.from_json(json.to_json(d1))
local eq2, path2 = deepeq(d1, d2)
assert(eq2, "JSON fidelity mismatch at " .. tostring(path2))
print("OK test_fidelity_live (" .. n .. " displays, " .. n2 .. " ours JSON-checked)")
