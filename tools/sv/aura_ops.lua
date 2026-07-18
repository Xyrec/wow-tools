local M = {}

local function deepcopy(t)
  if type(t) ~= "table" then return t end
  local out = {}
  for k, v in pairs(t) do out[k] = deepcopy(v) end
  return out
end

local UID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
local function gen_uid(displays)
  while true do
    local u = {}
    for i = 1, 11 do
      local r = math.random(#UID_CHARS)
      u[i] = UID_CHARS:sub(r, r)
    end
    local uid = table.concat(u)
    local clash = false
    for _, a in pairs(displays) do if a.uid == uid then clash = true break end end
    if not clash then return uid end
  end
end

function M.extract(displays, id)
  local root = displays[id]
  assert(root, "no display named " .. tostring(id))
  local c = {}
  local function walk(aura)
    for _, childId in ipairs(aura.controlledChildren or {}) do
      local child = displays[childId]
      assert(child, ("dangling controlledChildren ref %q in %q"):format(childId, aura.id))
      c[#c + 1] = deepcopy(child)
      walk(child)
    end
  end
  walk(root)
  local payload = { m = "d", v = 2000, s = "5.21.8", d = deepcopy(root) }
  if #c > 0 then payload.c = c end
  return payload
end

local function remove_aura(displays, id)
  local a = displays[id]
  if not a then return end
  if a.parent and displays[a.parent] and displays[a.parent].controlledChildren then
    local cc = displays[a.parent].controlledChildren
    for i = #cc, 1, -1 do if cc[i] == id then table.remove(cc, i) end end
  end
  for _, childId in ipairs(a.controlledChildren or {}) do
    remove_aura(displays, childId)
  end
  displays[id] = nil
end

function M.land(displays, payload, opts)
  opts = opts or {}
  assert(payload.d and payload.d.id, "payload has no root aura")
  local incoming = { deepcopy(payload.d) }
  for _, child in ipairs(payload.c or {}) do incoming[#incoming + 1] = deepcopy(child) end

  -- collision check BEFORE any mutation
  local collisions = {}
  for _, a in ipairs(incoming) do
    if displays[a.id] then collisions[#collisions + 1] = a.id end
  end
  if #collisions > 0 and not opts.delete then
    error("ids already exist (use --delete to replace): " .. table.concat(collisions, ", "))
  end
  if opts.parent then
    assert(displays[opts.parent], "parent does not exist: " .. opts.parent)
  end
  for _, id in ipairs(collisions) do remove_aura(displays, id) end

  local landed = {}
  for _, a in ipairs(incoming) do
    if not a.uid then a.uid = gen_uid(displays) end
    displays[a.id] = a
    landed[#landed + 1] = a.id
  end
  local root = displays[payload.d.id]
  if opts.parent then
    root.parent = opts.parent
    local cc = displays[opts.parent].controlledChildren
    if not cc then cc = {}; displays[opts.parent].controlledChildren = cc end
    cc[#cc + 1] = root.id
  end
  return landed
end

return M
