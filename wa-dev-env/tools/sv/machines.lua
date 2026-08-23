-- Per-machine configuration, selected by platform at runtime.
-- Single source of truth for game paths + the game-closed guard probe.
-- Add a machine: add a CONFIGS entry; nothing else in the repo changes.
local M = {}

local function uname()
  local p = io.popen("uname -s 2>/dev/null")
  local s = p and p:read("*l") or nil
  if p then p:close() end
  return s or "unknown"
end

local CONFIGS = {
  -- CachyOS PC (Lutris/Proton). Process name is "WoWClassic.exe" (capital O,
  -- unlike the on-disk file); name-matching is the only probe that works -
  -- -f cmdline probes self-match anything quoting the exe path.
  Linux = {
    wow_root = "/home/xyrec/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft/_anniversary_",
    guard_cmd = "pgrep -i wowclassic 2>/dev/null",
  },
  -- MacBook. [.] avoids the probe matching its own popen shell's cmdline.
  Darwin = {
    wow_root = "/Applications/World of Warcraft/_anniversary_",
    guard_cmd = "pgrep -f 'World of Warcraft[.]app/Contents/MacOS' 2>/dev/null",
  },
}

local cfg = assert(CONFIGS[uname()],
  "machines.lua: no config for platform '" .. uname() .. "'")

M.wow_root = cfg.wow_root
M.guard_cmd = cfg.guard_cmd
M.live_path = cfg.wow_root .. "/WTF/Account/THESNUB/SavedVariables/WeakAuras.lua"
M.dump_path = cfg.wow_root .. "/WTF/Account/THESNUB/SavedVariables/XyrecDump.lua"
M.addons_path = cfg.wow_root .. "/Interface/AddOns"

return M
