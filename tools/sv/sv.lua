-- SavedVariables I/O. Load = execute the file (it IS Lua) in an empty sandbox.
-- Save = deterministic Blizzard-style serialization (tabs, ["k"] = v, sorted keys).
local M = {}

M.LIVE_PATH = "/Applications/World of Warcraft/_anniversary_/WTF/Account/THESNUB/SavedVariables/WeakAuras.lua"

function M.load(path)
  local chunk, err = loadfile(path)
  assert(chunk, "cannot load " .. path .. ": " .. tostring(err))
  local env = {}
  setfenv(chunk, env)
  chunk()
  return env
end

local function qstr(s)
  -- %q escapes real newlines as backslash-newline; Blizzard writes \n
  return (string.format("%q", s):gsub("\\\n", "\\n"))
end

local function fmtnum(v)
  if math.floor(v) == v and math.abs(v) < 2 ^ 31 then return string.format("%d", v) end
  local s = string.format("%.14g", v)
  if tonumber(s) == v then return s end
  return string.format("%.17g", v)
end

local function sorted_keys(t)
  local nums, strs = {}, {}
  for k in pairs(t) do
    if type(k) == "number" then nums[#nums + 1] = k
    elseif type(k) == "string" then strs[#strs + 1] = k
    else error("unsupported key type in SavedVariables: " .. type(k)) end
  end
  table.sort(nums); table.sort(strs)
  local keys = {}
  for _, k in ipairs(nums) do keys[#keys + 1] = k end
  for _, k in ipairs(strs) do keys[#keys + 1] = k end
  return keys
end

local function ser(v, depth, out)
  local tv = type(v)
  if tv == "string" then out[#out + 1] = qstr(v)
  elseif tv == "number" then out[#out + 1] = fmtnum(v)
  elseif tv == "boolean" then out[#out + 1] = tostring(v)
  elseif tv == "table" then
    local pad = string.rep("\t", depth)
    out[#out + 1] = "{\n"
    for _, k in ipairs(sorted_keys(v)) do
      local kk = (type(k) == "number") and ("[" .. fmtnum(k) .. "]")
        or ("[" .. qstr(k) .. "]")
      out[#out + 1] = pad .. "\t" .. kk .. " = "
      ser(v[k], depth + 1, out)
      out[#out + 1] = ",\n"
    end
    out[#out + 1] = pad .. "}"
  else error("unsupported value type in SavedVariables: " .. tv) end
end

function M.save(path, env)
  local out = {}
  local names = {}
  for k in pairs(env) do names[#names + 1] = k end
  table.sort(names)
  for _, name in ipairs(names) do
    out[#out + 1] = name .. " = "
    ser(env[name], 0, out)
    out[#out + 1] = "\n"
  end
  local f = assert(io.open(path, "w"))
  f:write(table.concat(out))
  f:close()
end

return M
