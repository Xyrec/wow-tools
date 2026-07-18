-- deepeq(a, b) -> bool, path-of-first-difference
local function deepeq(a, b, path)
  path = path or "$"
  if a == b then return true end
  if type(a) ~= "table" or type(b) ~= "table" then return false, path end
  for k, v in pairs(a) do
    local ok, p = deepeq(v, b[k], path .. "." .. tostring(k))
    if not ok then return false, p end
  end
  for k in pairs(b) do
    if a[k] == nil then return false, path .. "." .. tostring(k) end
  end
  return true
end
return deepeq
