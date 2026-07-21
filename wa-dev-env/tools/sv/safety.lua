local sv = require("sv")
local M = {}

function M.assert_game_closed()
  if os.getenv("CCWOW_ALLOW_RUNNING") == "1" then return end
  local p = io.popen("pgrep -f 'World of Warcraft.app/Contents/MacOS' 2>/dev/null")
  local out = p:read("*a"); p:close()
  if out and out:match("%d") then
    error("World of Warcraft is running — it overwrites SavedVariables on logout. "
      .. "Close the game (or set CCWOW_ALLOW_RUNNING=1 if you know what you're doing).")
  end
end

function M.backup(src)
  -- CCWOW_BACKUP_DIR override exists so tests never pollute the real backups/
  local dir = os.getenv("CCWOW_BACKUP_DIR") or "backups"
  local stamp = os.date("%Y%m%d-%H%M%S")
  local dst = string.format("%s/WeakAuras-%s.lua", dir, stamp)
  local i = assert(io.open(src, "rb"), "cannot read " .. src)
  local data = i:read("*a"); i:close()
  os.execute("mkdir -p '" .. dir .. "'")
  local o = assert(io.open(dst, "wb")); o:write(data); o:close()
  return dst
end

function M.atomic_save(path, env)
  M.assert_game_closed()
  local tmp = path .. ".ccwow-tmp"
  sv.save(tmp, env)              -- errors on unserializable data BEFORE touching target
  sv.load(tmp)                   -- post-write reload check (spec §3.4)
  local existing = io.open(path, "r")
  if existing then existing:close(); M.backup(path) end
  assert(os.rename(tmp, path), "rename failed")
end

function M.restore(backupPath, targetPath)
  M.assert_game_closed()
  sv.load(backupPath)            -- never restore a corrupt backup
  local i = assert(io.open(backupPath, "rb")); local data = i:read("*a"); i:close()
  local o = assert(io.open(targetPath, "wb")); o:write(data); o:close()
end

return M
