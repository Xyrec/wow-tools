package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;" .. package.path
local codec = require("codec")
local deepeq = require("deepeq")

local payload = {
  m = "d", v = 2000, s = "5.21.8",
  d = { id = "Test Aura", regionType = "icon", uid = "abcDEF12345",
        triggers = { [1] = { trigger = { type = "aura2", auranames = { "Flame Shock" } } },
                     activeTriggerMode = -10 },
        load = { class = { multi = {} } } },
}
local s = codec.encode(payload)
assert(s:sub(1, 6) == "!WA:2!", "missing !WA:2! prefix, got: " .. s:sub(1, 10))
assert(not s:find("[\128-\255]"), "encode output not printable")
local p2 = codec.decode(s)
local eq, path = deepeq(payload, p2)
assert(eq, "round-trip mismatch at " .. tostring(path))
-- whitespace/newline tolerance (strings copied from chat/wago have wrapping)
local p3 = codec.decode("  " .. s:sub(1, 40) .. "\n" .. s:sub(41) .. " \n")
assert(deepeq(payload, p3), "whitespace-tolerant decode failed")
-- legacy detection
local ok, err = pcall(codec.decode, "!abcdef")
assert(not ok and tostring(err):find("legacy"), "legacy string should raise a 'legacy' error")
print("OK test_codec")
