package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local sv = require("sv")
local gt = require("groundtruth")

-- fixture mimicking XyrecDump SavedVariables
sv.save("tmp/XyrecDump_fixture.lua", { XyrecDumpDB = {
  spells = { [8050] = { name = "Flame Shock", rank = "Rank 1", icon = 135813 },
             [30455] = { name = "Ice Lance", icon = 135844 } },
  spells_meta = { build = "68775", when = "2026-07-18 20:00" },
  talents = { SHAMAN = { class = "SHAMAN", tabs = {
    [1] = { name = "Elemental", pointsSpent = 0, talents = {} } } } },
} })

os.execute("mkdir -p tmp/gt-out")
gt.import("tmp/XyrecDump_fixture.lua", "tmp/gt-out")
local json = require("json")
local f = assert(io.open("tmp/gt-out/spells.json"))
local spells = json.from_json(f:read("*a")); f:close()
assert(spells[8050].name == "Flame Shock", "spell import broken")
assert(spells[30455].name == "Ice Lance", "spell import broken (no-rank spell)")
local f2 = assert(io.open("tmp/gt-out/talents.json"))
local talents = json.from_json(f2:read("*a")); f2:close()
assert(talents.SHAMAN.tabs[1].name == "Elemental", "talent import broken")
print("OK test_groundtruth")
