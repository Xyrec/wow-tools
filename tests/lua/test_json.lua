package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;" .. package.path
local json = require("json")
local deepeq = require("deepeq")

-- mixed table exactly like WA's triggers: array part + string key
local t = {
  triggers = { [1] = { trigger = { type = "aura2" } }, activeTriggerMode = -10 },
  color = { 1, 0.5, 0, 0.75 },
  yOffset = -30.5,
  id = "Test \"Aura\"\nline2",
  big = 237583,
  flag = true,
}
local s = json.to_json(t)
assert(type(s) == "string" and s:find('"activeTriggerMode"'), "encode failed")
local t2 = json.from_json(s)
local eq, path = deepeq(t, t2)
assert(eq, "round-trip mismatch at " .. tostring(path))
-- numeric key survives as number, not string
assert(t2.triggers[1] ~= nil and t2.triggers["1"] == nil, "numeric key convention broken")
-- determinism
assert(s == json.to_json(t), "encoder not deterministic")
-- deepeq detects differences
local eq2 = deepeq({ a = 1 }, { a = 2 }); assert(eq2 == false, "deepeq false positive")
-- float precision survives
local f = { v = 0.1 + 0.2 }
local eqf = deepeq(f, json.from_json(json.to_json(f))); assert(eqf, "float precision lost")
print("OK test_json")
