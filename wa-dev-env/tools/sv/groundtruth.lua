local sv = require("sv")
local json = require("json")
local M = {}

M.DUMP_PATH = require("machines").dump_path

local function write_json(path, t)
  local f = assert(io.open(path, "w"))
  f:write(json.to_json(t))
  f:close()
end

function M.import(dumpPath, outDir)
  local env = sv.load(dumpPath)
  local db = assert(env.XyrecDumpDB, "no XyrecDumpDB in " .. dumpPath)
  if db.spells then
    write_json(outDir .. "/spells.json", db.spells)
    write_json(outDir .. "/spells_meta.json", db.spells_meta or {})
  end
  if db.talents then write_json(outDir .. "/talents.json", db.talents) end
  if db.spellbook then write_json(outDir .. "/spellbook.json", db.spellbook) end
  if db.aura_snapshots then write_json(outDir .. "/auras.json", db.aura_snapshots) end
  return true
end

return M
