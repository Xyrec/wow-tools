package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local ops = require("aura_ops")
local deepeq = require("deepeq")

local function mkdisplays()
  return {
    ["Group"] = { id = "Group", regionType = "group", uid = "GGGGGGGGGGG",
                  controlledChildren = { "Child A", "Child B" } },
    ["Child A"] = { id = "Child A", regionType = "icon", uid = "AAAAAAAAAAA", parent = "Group" },
    ["Child B"] = { id = "Child B", regionType = "dynamicgroup", uid = "BBBBBBBBBBB",
                    parent = "Group", controlledChildren = { "Grandchild" } },
    ["Grandchild"] = { id = "Grandchild", regionType = "aurabar", uid = "CCCCCCCCCCC",
                       parent = "Child B" },
    ["Other"] = { id = "Other", regionType = "icon", uid = "DDDDDDDDDDD" },
  }
end

-- extract gathers the subtree in transmission shape
local d = mkdisplays()
local payload = ops.extract(d, "Group")
assert(payload.m == "d" and payload.v == 2000, "payload shape wrong")
assert(payload.d.id == "Group", "root wrong")
assert(#payload.c == 3, "expected 3 descendants, got " .. #payload.c)

-- extract of a leaf has no c
local leaf = ops.extract(d, "Other")
assert(leaf.c == nil, "leaf should have no children array")

-- land into a fresh displays table under a new parent
local dst = { ["Target Parent"] = { id = "Target Parent", regionType = "group",
                                    uid = "TTTTTTTTTTT", controlledChildren = {} } }
local landed = ops.land(dst, payload, { parent = "Target Parent" })
assert(dst["Group"] and dst["Grandchild"], "descendants not landed")
assert(dst["Group"].parent == "Target Parent", "parent not set")
assert(dst["Target Parent"].controlledChildren[1] == "Group", "controlledChildren not updated")
assert(dst["Grandchild"].parent == "Child B", "internal parent links must be preserved")

-- collision without --delete errors and leaves dst unchanged
local before = ops.extract(dst, "Target Parent")
local ok = pcall(ops.land, dst, payload, { parent = "Target Parent" })
assert(not ok, "landing over existing ids must error without delete")
assert(deepeq(before, ops.extract(dst, "Target Parent")), "failed land must not mutate")

-- collision with delete replaces
ops.land(dst, payload, { parent = "Target Parent", delete = true })
assert(dst["Group"], "replace failed")
local count = 0
for _, c in ipairs(dst["Target Parent"].controlledChildren) do
  if c == "Group" then count = count + 1 end
end
assert(count == 1, "duplicate controlledChildren entry after replace")

-- uid generated when missing, unique, 11 chars
local nouid = { m = "d", v = 2000, s = "5.21.8",
                d = { id = "NoUid", regionType = "icon" } }
ops.land(dst, nouid, {})
assert(dst["NoUid"].uid and #dst["NoUid"].uid == 11, "uid not generated")
print("OK test_aura_ops")

-- remove deletes an aura and unlinks it from its parent
local d2 = mkdisplays()
require("aura_ops").remove(d2, "Child B")
assert(d2["Child B"] == nil and d2["Grandchild"] == nil, "remove must delete subtree")
for _, c in ipairs(d2["Group"].controlledChildren) do
  assert(c ~= "Child B", "removed child still referenced by parent")
end
print("OK test_aura_ops remove")
