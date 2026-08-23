-- Exactly WeakAuras Transmission.lua's pipeline (v2 / !WA:2!).
local env = require("env")
local LS, LD = env.LibSerialize, env.LibDeflate
local M = {}

function M.encode(payload)
  local ser = LS:SerializeEx({ errorOnUnserializableType = false }, payload)
  local comp = LD:CompressDeflate(ser, { level = 9 })
  return "!WA:2!" .. LD:EncodeForPrint(comp)
end

function M.decode(s)
  s = s:gsub("%s", "")
  local ver, body = s:match("^!WA:(%d+)!(.+)$")
  if ver then
    assert(tonumber(ver) == 2, "unsupported !WA:" .. ver .. "! format")
    local comp = assert(LD:DecodeForPrint(body), "DecodeForPrint failed (corrupt string?)")
    local ser = assert(LD:DecompressDeflate(comp), "DecompressDeflate failed")
    local ok, payload = LS:Deserialize(ser)
    assert(ok, "LibSerialize:Deserialize failed: " .. tostring(payload))
    return payload
  end
  if s:sub(1, 1) == "!" or #s > 0 then
    error("legacy (pre-!WA:2!) export string - not supported (spec §7); re-export from a current WeakAuras")
  end
  error("empty input")
end

return M
