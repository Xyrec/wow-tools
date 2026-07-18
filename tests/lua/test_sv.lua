package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local sv = require("sv")
local deepeq = require("deepeq")

-- fixture in Blizzard's own style
local fixture = 'tmp/test_sv_fixture.lua'
local f = assert(io.open(fixture, "w"))
f:write([[
XyrecTestDB = {
	["displays"] = {
		["A \"quoted\" name"] = {
			["yOffset"] = -30.5,
			["controlledChildren"] = {
				"child1", -- comment survives loading (it's real Lua)
			},
			[1] = true,
			["desc"] = "line1\nline2",
		},
	},
	["num"] = 470,
}
OtherGlobal = "kept"
]])
f:close()

local env1 = sv.load(fixture)
assert(env1.XyrecTestDB.num == 470, "load failed")
assert(env1.XyrecTestDB.displays['A "quoted" name'].desc == "line1\nline2", "string escape broken")
assert(env1.OtherGlobal == "kept", "second global lost")

sv.save("tmp/test_sv_out.lua", env1)
local env2 = sv.load("tmp/test_sv_out.lua")
local eq, path = deepeq(env1, env2)
assert(eq, "save/load mismatch at " .. tostring(path))
-- determinism
sv.save("tmp/test_sv_out2.lua", env2)
local a = io.open("tmp/test_sv_out.lua"):read("*a")
local b = io.open("tmp/test_sv_out2.lua"):read("*a")
assert(a == b, "writer not deterministic")
print("OK test_sv")
