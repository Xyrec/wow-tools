-- Canonical JSON layer. Convention:
--   Lua array (consecutive int keys 1..n, no others) <-> JSON array
--   any other table <-> JSON object; numeric keys <-> decimal-string keys
--   decode converts object keys matching ^-?%d+$ / ^-?%d+%.%d+$ back to numbers.
-- Deterministic output: numeric keys first (ascending), then string keys (alpha).
local dkjson = require("dkjson")
local M = {}

local function fmtnum(v)
  if v ~= v or v == math.huge or v == -math.huge then error("non-finite number") end
  if math.floor(v) == v and math.abs(v) < 2 ^ 31 then return string.format("%d", v) end
  local s = string.format("%.14g", v)
  if tonumber(s) == v then return s end
  return string.format("%.17g", v)
end

local ESC = { ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f",
  ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }
local function fmtstr(s)
  return '"' .. s:gsub('[%z\1-\31"\\]', function(c)
    return ESC[c] or string.format("\\u%04x", c:byte())
  end) .. '"'
end

local function is_array(t)
  local n = 0
  for k in pairs(t) do
    if type(k) ~= "number" or k ~= math.floor(k) or k < 1 then return false end
    n = n + 1
  end
  for i = 1, n do if t[i] == nil then return false end end
  return true, n
end

local function enc(v, indent, out)
  local tv = type(v)
  if tv == "string" then out[#out + 1] = fmtstr(v)
  elseif tv == "number" then out[#out + 1] = fmtnum(v)
  elseif tv == "boolean" then out[#out + 1] = tostring(v)
  elseif tv == "table" then
    local pad, pad2 = string.rep("  ", indent), string.rep("  ", indent + 1)
    local arr, n = is_array(v)
    if arr then
      if n == 0 then out[#out + 1] = "[]" return end
      out[#out + 1] = "[\n"
      for i = 1, n do
        out[#out + 1] = pad2
        enc(v[i], indent + 1, out)
        out[#out + 1] = (i < n) and ",\n" or "\n"
      end
      out[#out + 1] = pad .. "]"
    else
      local nums, strs = {}, {}
      for k in pairs(v) do
        local tk = type(k)
        if tk == "number" then nums[#nums + 1] = k
        elseif tk == "string" then strs[#strs + 1] = k
        else error("unsupported key type: " .. tk) end
      end
      table.sort(nums); table.sort(strs)
      local keys = {}
      for _, k in ipairs(nums) do keys[#keys + 1] = k end
      for _, k in ipairs(strs) do keys[#keys + 1] = k end
      if #keys == 0 then out[#out + 1] = "{}" return end
      out[#out + 1] = "{\n"
      for i, k in ipairs(keys) do
        out[#out + 1] = pad2 .. fmtstr(type(k) == "number" and fmtnum(k) or k) .. ": "
        enc(v[k], indent + 1, out)
        out[#out + 1] = (i < #keys) and ",\n" or "\n"
      end
      out[#out + 1] = pad .. "}"
    end
  else error("unsupported value type: " .. tv) end
end

function M.to_json(t)
  local out = {}
  enc(t, 0, out)
  return table.concat(out) .. "\n"
end

local function revive(v)
  if type(v) ~= "table" then return v end
  local out = {}
  for k, val in pairs(v) do
    local nk = k
    if type(k) == "string" and (k:match("^-?%d+$") or k:match("^-?%d+%.%d+$")) then
      nk = tonumber(k)
    end
    out[nk] = revive(val)
  end
  return out
end

function M.from_json(s)
  local t, _, err = dkjson.decode(s, 1, nil)
  if err then error("JSON decode error: " .. tostring(err)) end
  return revive(t)
end

return M
