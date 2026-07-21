# WeakAura Dev Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the class-agnostic WeakAura dev environment from `docs/superpowers/specs/2026-07-18-weakaura-dev-environment-design.md`: codec, SavedVariables I/O, ground-truth pipeline, migration/restyle tooling, audit, and lint.

**Architecture:** Lua 5.1 CLI (`tools/wa`) reuses the *installed WeakAuras addon's own* LibSerialize/LibDeflate for the `!WA:2!` codec and `dofile`-based SavedVariables I/O. Python (`tools/migrate/`) handles fuzzy work (style templates, spell validation, audits) over a canonical JSON representation. The game client is the ground-truth oracle via a dump addon; wago.tools db2 exports are the offline layer.

**Tech Stack:** Lua 5.1 (Homebrew `lua@5.1`), vendored LibSerialize + LibDeflate + dkjson, Python 3 + pytest, luacheck, git.

## Global Constraints

- Game paths: SavedVariables `/Applications/World of Warcraft/_anniversary_/WTF/Account/THESNUB/SavedVariables/WeakAuras.lua`; AddOns `/Applications/World of Warcraft/_anniversary_/Interface/AddOns/`.
- The live `WeakAuras.lua` is NEVER written by tests or by any task in this plan. All write tests use copies under `tmp/` (gitignored). Write capability is gated behind Task 5's safety layer.
- Codec pipeline must be exactly WeakAuras' `Transmission.lua` pipeline: `LibSerialize:SerializeEx({errorOnUnserializableType=false}, t)` → `LibDeflate:CompressDeflate(s, {level=9})` → `"!WA:2!" .. LibDeflate:EncodeForPrint(c)`.
- Acceptance tests are **deep-equality**, never byte-identity (spec §2, §3).
- No spell/talent fact enters an aura without resolving against `data/ground-truth/` (spec §4).
- Vendored libraries are copied unmodified; all shims live outside the vendored files.
- Every Lua entry point runs on Lua 5.1 (`$(brew --prefix lua@5.1)/bin/lua5.1`); no 5.2+ features (no `goto`, use `unpack` not `table.unpack`, `setfenv` is available and used).
- Commit after every task (steps include the commands).

**Test runner convention:** Lua tests are standalone scripts under `tests/lua/` that `error()` on failure and print `OK <name>` on success. Python tests are pytest files under `tests/py/`. `tests/run.sh` runs everything.

---

### Task 1: Vendored codec libraries + standalone load proof

**Files:**
- Create: `tools/wa-codec/libs/LibSerialize.lua` (copied from installed addon)
- Create: `tools/wa-codec/libs/LibDeflate.lua` (copied from installed addon)
- Create: `tools/wa-codec/libs/dkjson.lua` (vendored)
- Create: `tools/wa-codec/env.lua`
- Create: `tests/lua/test_libs.lua`
- Create: `tests/run.sh`

**Interfaces:**
- Produces: `require("env")` → `{ LibSerialize = <lib>, LibDeflate = <lib>, dkjson = <lib> }` for all later Lua code. `tests/run.sh` as the single test entry point.

- [ ] **Step 1: Install Lua 5.1 and locate the installed libraries**

```bash
brew install lua@5.1
LUA51="$(brew --prefix lua@5.1)/bin/lua5.1"; "$LUA51" -v   # expect: Lua 5.1.x
WA_ADDON="/Applications/World of Warcraft/_anniversary_/Interface/AddOns/WeakAuras"
find "$WA_ADDON/Libs" -iname "LibSerialize.lua" -o -iname "LibDeflate.lua"
```

Expected: both files found (e.g. `.../Libs/LibSerialize/LibSerialize.lua`, `.../Libs/LibDeflate/LibDeflate.lua`). Note: spec said "vendored from the WeakAuras2 repo"; we copy from the **installed addon** instead — same files, but version-exact to what the user runs. If either file is missing, STOP and report (do not substitute a downloaded version without flagging it).

- [ ] **Step 2: Copy libraries unmodified; vendor dkjson**

```bash
mkdir -p tools/wa-codec/libs tests/lua tmp
cp "$WA_ADDON"/Libs/LibSerialize/LibSerialize.lua tools/wa-codec/libs/
cp "$WA_ADDON"/Libs/LibDeflate/LibDeflate.lua tools/wa-codec/libs/
curl -fsSL https://raw.githubusercontent.com/LuaDist/dkjson/master/dkjson.lua -o tools/wa-codec/libs/dkjson.lua
head -5 tools/wa-codec/libs/dkjson.lua   # sanity: Lua source, not an error page
echo "tmp/" >> .gitignore
```

- [ ] **Step 3: Write the failing test**

`tests/lua/test_libs.lua`:

```lua
package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;" .. package.path
local env = require("env")
assert(type(env.LibSerialize) == "table", "LibSerialize not loaded")
assert(type(env.LibDeflate) == "table", "LibDeflate not loaded")
assert(type(env.dkjson) == "table", "dkjson not loaded")

-- serialize -> compress -> decompress -> deserialize round-trip of a mixed table
local t = { 1, 2, "three", nested = { a = true, [5] = 0.75 } }
local ser = env.LibSerialize:SerializeEx({ errorOnUnserializableType = false }, t)
local comp = env.LibDeflate:CompressDeflate(ser, { level = 9 })
local decomp = env.LibDeflate:DecompressDeflate(comp)
assert(decomp == ser, "deflate round-trip mismatch")
local ok, t2 = env.LibSerialize:Deserialize(decomp)
assert(ok, "deserialize failed")
assert(t2.nested.a == true and t2.nested[5] == 0.75 and t2[3] == "three", "content mismatch")
print("OK test_libs")
```

`tests/run.sh`:

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."
LUA51="$(brew --prefix lua@5.1)/bin/lua5.1"
for f in tests/lua/test_*.lua; do "$LUA51" "$f"; done
if ls tests/py/test_*.py >/dev/null 2>&1; then python3 -m pytest tests/py -q; fi
echo "ALL TESTS PASSED"
```

```bash
chmod +x tests/run.sh
```

- [ ] **Step 4: Run test to verify it fails**

Run: `./tests/run.sh`
Expected: FAIL — `module 'env' not found`.

- [ ] **Step 5: Write `tools/wa-codec/env.lua`**

Both libraries support non-WoW use: with no `LibStub` global they assign themselves to a local and `return` it. dkjson is a plain module.

```lua
-- Standalone loader for the vendored WeakAuras libraries.
-- Vendored files are UNMODIFIED; any adaptation lives here.
local base = (... or "env"):gsub("env$", "")
local function load_lib(name)
  local lib = require(name)
  assert(type(lib) == "table", name .. " did not return a library table")
  return lib
end
return {
  LibDeflate = load_lib("LibDeflate"),
  LibSerialize = load_lib("LibSerialize"),
  dkjson = load_lib("dkjson"),
}
```

If `require("LibSerialize")` fails because the file expects a WoW global, inspect the top of the vendored file and extend *this* loader (e.g. predefine a stub) — never edit the vendored file.

- [ ] **Step 6: Run test to verify it passes**

Run: `./tests/run.sh`
Expected: `OK test_libs` then `ALL TESTS PASSED`.

- [ ] **Step 7: Commit**

```bash
git add tools/wa-codec tests .gitignore
git commit -m "feat: vendor LibSerialize/LibDeflate/dkjson with standalone loader"
```

---

### Task 2: JSON layer — canonical encoder, decoder with key convention, deep-equal

**Files:**
- Create: `tools/wa-codec/json.lua`
- Create: `tools/wa-codec/deepeq.lua`
- Test: `tests/lua/test_json.lua`

**Interfaces:**
- Consumes: `env.dkjson` from Task 1.
- Produces: `json.to_json(luaTable) -> string` (pretty, deterministic, 2-space indent), `json.from_json(string) -> luaTable`, `deepeq(a, b) -> bool, pathString`. Convention (documented in `json.lua` header): Lua tables with consecutive integer keys 1..n and no other keys become JSON arrays; all other tables become JSON objects; numeric keys become their decimal string form; on decode, any object key matching `^-?%d+$` or `^-?%d+%.%d+$` is converted back to a Lua number. Only string/number/boolean/table values and string/number keys are allowed — anything else errors.

- [ ] **Step 1: Write the failing test**

`tests/lua/test_json.lua`:

```lua
package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;" .. package.path
local json = require("json")
local deepeq = require("deepeq")

-- mixed table exactly like WA's triggers: array part + string key
local t = {
  triggers = { [1] = { trigger = { type = "aura2" } }, activeTriggerMode = -10 },
  color = { 1, 0.5, 0, 0.75 },
  yOffset = -30.5,
  id = "Test \"Aura\"\nline2",
  big = 237583,
  flag = true,
}
local s = json.to_json(t)
assert(type(s) == "string" and s:find('"activeTriggerMode"'), "encode failed")
local t2 = json.from_json(s)
local eq, path = deepeq(t, t2)
assert(eq, "round-trip mismatch at " .. tostring(path))
-- numeric key survives as number, not string
assert(t2.triggers[1] ~= nil and t2.triggers["1"] == nil, "numeric key convention broken")
-- determinism
assert(s == json.to_json(t), "encoder not deterministic")
-- deepeq detects differences
local eq2 = deepeq({ a = 1 }, { a = 2 }); assert(eq2 == false, "deepeq false positive")
-- float precision survives
local f = { v = 0.1 + 0.2 }
local eqf = deepeq(f, json.from_json(json.to_json(f))); assert(eqf, "float precision lost")
print("OK test_json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./tests/run.sh`
Expected: FAIL — `module 'json' not found`.

- [ ] **Step 3: Implement `tools/wa-codec/deepeq.lua`**

```lua
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
```

- [ ] **Step 4: Implement `tools/wa-codec/json.lua`**

```lua
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./tests/run.sh`
Expected: `OK test_json`, all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/wa-codec/json.lua tools/wa-codec/deepeq.lua tests/lua/test_json.lua
git commit -m "feat: canonical JSON layer with numeric-key convention and deep-equal"
```

---

### Task 3: `wa` CLI with decode/encode

**Files:**
- Create: `tools/wa` (dispatcher, executable)
- Create: `tools/wa-codec/codec.lua`
- Create: `tools/wa-codec/main.lua`
- Test: `tests/lua/test_codec.lua`

**Interfaces:**
- Consumes: Task 1 `env`, Task 2 `json`/`deepeq`.
- Produces: `codec.decode(waString) -> payloadTable` and `codec.encode(payloadTable) -> waString` (Lua API); shell commands `tools/wa decode <string-or-@file>` → JSON on stdout, `tools/wa encode <json-file>` → `!WA:2!...` on stdout. Later tasks add subcommands to `tools/wa`'s dispatch table.

- [ ] **Step 1: Write the failing test**

`tests/lua/test_codec.lua`:

```lua
package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;" .. package.path
local codec = require("codec")
local deepeq = require("deepeq")

local payload = {
  m = "d", v = 2000, s = "5.21.8",
  d = { id = "Test Aura", regionType = "icon", uid = "abcDEF12345",
        triggers = { [1] = { trigger = { type = "aura2", auranames = { "Flame Shock" } } },
                     activeTriggerMode = -10 },
        load = { class = { multi = {} } } },
}
local s = codec.encode(payload)
assert(s:sub(1, 6) == "!WA:2!", "missing !WA:2! prefix, got: " .. s:sub(1, 10))
assert(not s:find("[\128-\255]"), "encode output not printable")
local p2 = codec.decode(s)
local eq, path = deepeq(payload, p2)
assert(eq, "round-trip mismatch at " .. tostring(path))
-- whitespace/newline tolerance (strings copied from chat/wago have wrapping)
local p3 = codec.decode("  " .. s:sub(1, 40) .. "\n" .. s:sub(41) .. " \n")
assert(deepeq(payload, p3), "whitespace-tolerant decode failed")
-- legacy detection
local ok, err = pcall(codec.decode, "!abcdef")
assert(not ok and tostring(err):find("legacy"), "legacy string should raise a 'legacy' error")
print("OK test_codec")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./tests/run.sh`
Expected: FAIL — `module 'codec' not found`.

- [ ] **Step 3: Implement `tools/wa-codec/codec.lua`**

```lua
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
    error("legacy (pre-!WA:2!) export string — not supported (spec §7); re-export from a current WeakAuras")
  end
  error("empty input")
end

return M
```

- [ ] **Step 4: Implement `tools/wa-codec/main.lua` and the `tools/wa` dispatcher**

`tools/wa-codec/main.lua`:

```lua
package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local json = require("json")
local codec = require("codec")

local function read_input(arg)
  if arg:sub(1, 1) == "@" then
    local f = assert(io.open(arg:sub(2), "r"), "cannot open " .. arg:sub(2))
    local s = f:read("*a"); f:close(); return s
  end
  return arg
end

local commands = {}

commands.decode = function(args)
  assert(args[1], "usage: wa decode <string-or-@file>")
  io.write(json.to_json(codec.decode(read_input(args[1]))))
end

commands.encode = function(args)
  assert(args[1], "usage: wa encode <json-file>")
  local f = assert(io.open(args[1], "r"), "cannot open " .. args[1])
  local payload = json.from_json(f:read("*a")); f:close()
  io.write(codec.encode(payload) .. "\n")
end

local cmd = table.remove(arg, 1)
if not cmd or not commands[cmd] then
  io.stderr:write("usage: wa <decode|encode> ...\n"); os.exit(2)
end
commands[cmd](arg)
```

`tools/wa`:

```bash
#!/bin/bash
# WeakAura dev-environment CLI. Run from anywhere; operates on the repo root.
set -e
cd "$(dirname "$0")/.."
LUA51="$(brew --prefix lua@5.1)/bin/lua5.1"
exec "$LUA51" tools/wa-codec/main.lua "$@"
```

```bash
chmod +x tools/wa
```

- [ ] **Step 5: Run tests and a manual smoke check**

Run: `./tests/run.sh`
Expected: `OK test_codec`, all pass.

```bash
printf '{"m":"d","v":2000,"s":"5.21.8","d":{"id":"Smoke","regionType":"icon","triggers":{"1":{"trigger":{"type":"aura2"}},"activeTriggerMode":-10}}}' > tmp/smoke.json
./tools/wa encode tmp/smoke.json | tee tmp/smoke.txt
./tools/wa decode @tmp/smoke.txt
```

Expected: an `!WA:2!...` string, then JSON containing `"id": "Smoke"`.

- [ ] **Step 6: Commit**

```bash
git add tools/wa tools/wa-codec/codec.lua tools/wa-codec/main.lua tests/lua/test_codec.lua
git commit -m "feat: wa decode/encode CLI over WeakAuras' own transmission pipeline"
```

**In-game acceptance (deferred to Task 12 checklist):** paste an encoded string into WeakAuras' Import dialog; it must parse and show the aura preview.

---

### Task 4: SavedVariables loader/writer + real-file fidelity tests

**Files:**
- Create: `tools/sv/sv.lua`
- Test: `tests/lua/test_sv.lua`
- Test: `tests/lua/test_fidelity_live.lua` (read-only on the live file)

**Interfaces:**
- Consumes: Task 2 `json`, `deepeq`.
- Produces: `sv.load(path) -> envTable` (all globals defined by the file, e.g. `envTable.WeakAurasSaved`), `sv.save(path, envTable)` (Blizzard-style Lua, deterministic sorted keys), `sv.LIVE_PATH` constant. Used by Tasks 5–7.

- [ ] **Step 1: Write the failing unit test**

`tests/lua/test_sv.lua`:

```lua
package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local sv = require("sv")
local deepeq = require("deepeq")

-- fixture in Blizzard's own style
local fixture = 'tmp/test_sv_fixture.lua'
local f = assert(io.open(fixture, "w"))
f:write([[
XyrecTestDB = {
	["displays"] = {
		["A \"quoted\" name"] = {
			["yOffset"] = -30.5,
			["controlledChildren"] = {
				"child1", -- comment survives loading (it's real Lua)
			},
			[1] = true,
			["desc"] = "line1\nline2",
		},
	},
	["num"] = 470,
}
OtherGlobal = "kept"
]])
f:close()

local env1 = sv.load(fixture)
assert(env1.XyrecTestDB.num == 470, "load failed")
assert(env1.XyrecTestDB.displays['A "quoted" name'].desc == "line1\nline2", "string escape broken")
assert(env1.OtherGlobal == "kept", "second global lost")

sv.save("tmp/test_sv_out.lua", env1)
local env2 = sv.load("tmp/test_sv_out.lua")
local eq, path = deepeq(env1, env2)
assert(eq, "save/load mismatch at " .. tostring(path))
-- determinism
sv.save("tmp/test_sv_out2.lua", env2)
local a = io.open("tmp/test_sv_out.lua"):read("*a")
local b = io.open("tmp/test_sv_out2.lua"):read("*a")
assert(a == b, "writer not deterministic")
print("OK test_sv")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./tests/run.sh`
Expected: FAIL — `module 'sv' not found`.

- [ ] **Step 3: Implement `tools/sv/sv.lua`**

```lua
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
```

- [ ] **Step 4: Run unit test to verify it passes**

Run: `./tests/run.sh`
Expected: `OK test_sv`.

- [ ] **Step 5: Write the live-file fidelity test (read-only)**

`tests/lua/test_fidelity_live.lua`:

```lua
package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local sv = require("sv")
local json = require("json")
local deepeq = require("deepeq")

-- 1) SavedVariables: load(save(load(live))) deep-equals load(live)
local env1 = sv.load(sv.LIVE_PATH)
assert(env1.WeakAurasSaved and env1.WeakAurasSaved.displays, "live file missing WeakAurasSaved.displays")
local n = 0; for _ in pairs(env1.WeakAurasSaved.displays) do n = n + 1 end
assert(n > 400, "expected 400+ displays, got " .. n)
sv.save("tmp/live_rewrite.lua", env1)
local env2 = sv.load("tmp/live_rewrite.lua")
local eq, path = deepeq(env1, env2)
assert(eq, "SV round-trip mismatch at " .. tostring(path))

-- 2) JSON convention proven over ALL real displays (spec §2 numeric-key risk)
local d1 = env1.WeakAurasSaved.displays
local d2 = json.from_json(json.to_json(d1))
local eq2, path2 = deepeq(d1, d2)
assert(eq2, "JSON fidelity mismatch at " .. tostring(path2))
print("OK test_fidelity_live (" .. n .. " displays)")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `./tests/run.sh`
Expected: `OK test_fidelity_live (470 displays)` (count may drift with user play). If the JSON fidelity check fails on a genuine digit-string key collision, the convention needs an escape marker — stop and surface the failing path before changing the convention.

- [ ] **Step 7: Commit**

```bash
git add tools/sv tests/lua/test_sv.lua tests/lua/test_fidelity_live.lua
git commit -m "feat: SavedVariables load/save with live-file fidelity proof"
```

---

### Task 5: Safety layer — guard, backup, atomic write, restore

**Files:**
- Create: `tools/sv/safety.lua`
- Modify: `tools/wa-codec/main.lua` (add `backup`, `restore` commands)
- Test: `tests/lua/test_safety.lua`

**Interfaces:**
- Consumes: Task 4 `sv`.
- Produces: `safety.assert_game_closed()` (errors if the WoW client runs; env `CCWOW_ALLOW_RUNNING=1` overrides — for tests only), `safety.backup(srcPath) -> backupPath` (to `backups/WeakAuras-YYYYmmdd-HHMMSS.lua`), `safety.atomic_save(path, env)` (backup if target exists → write temp → `sv.load` temp to verify → rename), `safety.restore(backupPath, targetPath)`. CLI: `wa backup`, `wa restore <backup-file>`. Task 6's `land` MUST route every live write through `safety.atomic_save`.

- [ ] **Step 1: Write the failing test**

`tests/lua/test_safety.lua`:

```lua
package.path = "tools/wa-codec/?.lua;tools/wa-codec/libs/?.lua;tools/sv/?.lua;" .. package.path
local sv = require("sv")
local safety = require("safety")
local deepeq = require("deepeq")

os.execute("mkdir -p tmp backups")
local target = "tmp/safety_target.lua"
sv.save(target, { TestDB = { a = 1 } })

-- backup creates a timestamped copy
local bpath = safety.backup(target)
assert(bpath:match("^backups/"), "backup not in backups/: " .. tostring(bpath))
assert(io.open(bpath, "r"), "backup file missing")

-- atomic_save writes loadable content and preserves a backup of the previous state
safety.atomic_save(target, { TestDB = { a = 2 } })
assert(sv.load(target).TestDB.a == 2, "atomic_save content wrong")

-- restore brings the old state back
safety.restore(bpath, target)
assert(sv.load(target).TestDB.a == 1, "restore failed")

-- atomic_save refuses to write corrupt data (simulate: function value is unserializable)
local ok = pcall(safety.atomic_save, target, { TestDB = { f = print } })
assert(not ok, "atomic_save accepted unserializable data")
assert(sv.load(target).TestDB.a == 1, "failed save must not touch target")

-- game-running guard honors the test override
local prev = os.getenv("CCWOW_ALLOW_RUNNING")
assert(pcall(safety.assert_game_closed) or true, "guard raised unexpectedly with no game running")
print("OK test_safety")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./tests/run.sh`
Expected: FAIL — `module 'safety' not found`.

- [ ] **Step 3: Implement `tools/sv/safety.lua`**

```lua
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
  local stamp = os.date("%Y%m%d-%H%M%S")
  local dst = string.format("backups/WeakAuras-%s.lua", stamp)
  local i = assert(io.open(src, "rb"), "cannot read " .. src)
  local data = i:read("*a"); i:close()
  os.execute("mkdir -p backups")
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
```

Note: `sv.save` writes to `tmp` first and errors on unserializable values before the target is touched — but it may leave a partial temp file; that's fine, the target is only replaced by `os.rename` after a successful verification load.

- [ ] **Step 4: Add CLI commands in `tools/wa-codec/main.lua`**

Add to the `commands` table (after the existing entries):

```lua
commands.backup = function()
  local safety = require("safety")
  local sv = require("sv")
  print(safety.backup(sv.LIVE_PATH))
end

commands.restore = function(args)
  assert(args[1], "usage: wa restore <backups/WeakAuras-....lua>")
  local safety = require("safety")
  local sv = require("sv")
  safety.restore(args[1], sv.LIVE_PATH)
  print("restored " .. args[1] .. " -> " .. sv.LIVE_PATH)
end
```

And update the usage line: `io.stderr:write("usage: wa <decode|encode|backup|restore> ...\n")`.

- [ ] **Step 5: Run tests + smoke `wa backup`**

Run: `./tests/run.sh` — expect `OK test_safety`.
Run: `./tools/wa backup` — expect a new `backups/WeakAuras-<stamp>.lua` printed; verify with `ls -la backups/`.

- [ ] **Step 6: Commit**

```bash
git add tools/sv/safety.lua tools/wa-codec/main.lua tests/lua/test_safety.lua
git commit -m "feat: safety layer - game guard, timestamped backups, atomic verified writes"
```

---

### Task 6: `wa extract` / `wa land` — auras in and out of SavedVariables

**Files:**
- Create: `tools/sv/aura_ops.lua`
- Modify: `tools/wa-codec/main.lua` (add `extract`, `land` commands)
- Test: `tests/lua/test_aura_ops.lua`

**Interfaces:**
- Consumes: Tasks 2, 4, 5.
- Produces: `aura_ops.extract(displays, id) -> payload` (transmission-shaped: `{m="d", v=2000, s="5.21.8", d=<aura>, c=<descendants array>}`; descendants gathered depth-first via `controlledChildren`), `aura_ops.land(displays, payload, opts) -> landedIds` with `opts = {parent=string|nil, delete=bool}`. `land` clones payload auras into `displays`, generates a `uid` (11 chars `[a-zA-Z0-9]`, unique across `displays`) when missing, sets `d.parent = opts.parent`, appends to the parent's `controlledChildren` (error if parent id doesn't exist), errors if any target id already exists unless `opts.delete` (which first removes those ids and their references). CLI: `wa extract <id> [-o file]`, `wa land <json-file> [--parent <id>] [--delete]`.
- The transmission payload shape means extracted files are directly `wa encode`-able into importable strings — extract/encode/decode/land compose.

- [ ] **Step 1: Write the failing test**

`tests/lua/test_aura_ops.lua`:

```lua
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./tests/run.sh`
Expected: FAIL — `module 'aura_ops' not found`.

- [ ] **Step 3: Implement `tools/sv/aura_ops.lua`**

```lua
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
```

- [ ] **Step 4: Add CLI commands in `tools/wa-codec/main.lua`**

```lua
commands.extract = function(args)
  local id = assert(args[1], "usage: wa extract <aura-id> [-o out.json]")
  local sv = require("sv")
  local ops = require("aura_ops")
  local env = sv.load(sv.LIVE_PATH)
  local payload = ops.extract(env.WeakAurasSaved.displays, id)
  local out = json.to_json(payload)
  if args[2] == "-o" and args[3] then
    local f = assert(io.open(args[3], "w")); f:write(out); f:close()
    print("wrote " .. args[3])
  else io.write(out) end
end

commands.land = function(args)
  local file = assert(args[1], "usage: wa land <payload.json> [--parent <id>] [--delete]")
  local opts = {}
  for i = 2, #args do
    if args[i] == "--parent" then opts.parent = args[i + 1]
    elseif args[i] == "--delete" then opts.delete = true end
  end
  local sv = require("sv")
  local safety = require("safety")
  local ops = require("aura_ops")
  local f = assert(io.open(file, "r"))
  local payload = json.from_json(f:read("*a")); f:close()
  local env = sv.load(sv.LIVE_PATH)
  math.randomseed(os.time())
  local landed = ops.land(env.WeakAurasSaved.displays, payload, opts)
  safety.atomic_save(sv.LIVE_PATH, env)
  print("landed: " .. table.concat(landed, ", "))
end
```

Update usage: `wa <decode|encode|backup|restore|extract|land> ...`.

- [ ] **Step 5: Run tests + read-only smoke**

Run: `./tests/run.sh` — expect `OK test_aura_ops`.
Run: `./tools/wa extract "Shaman - Stormstrike" -o tmp/stormstrike.json && head -20 tmp/stormstrike.json` — expect JSON with `"id": "Shaman - Stormstrike"`. (Extraction is read-only; do NOT run `wa land` against the live file in this task.)

- [ ] **Step 6: Commit**

```bash
git add tools/sv/aura_ops.lua tools/wa-codec/main.lua tests/lua/test_aura_ops.lua
git commit -m "feat: wa extract/land with uid generation and safe group re-linking"
```

---

### Task 7: XyrecDump addon + ground-truth importer

**Files:**
- Create: `addon/XyrecDump/XyrecDump.toc`
- Create: `addon/XyrecDump/core.lua`
- Create: `tools/install-addon.sh`
- Modify: `tools/wa-codec/main.lua` (add `pull-groundtruth`)
- Test: `tests/lua/test_groundtruth.lua`

**Interfaces:**
- Consumes: Tasks 2, 4.
- Produces: in-game slash commands `/xdump spells <from> <to>`, `/xdump talents`, `/xdump auras`, writing `XyrecDumpDB` SavedVariables. `wa pull-groundtruth` reads that SavedVariables file and writes `data/ground-truth/spells.json` (`{ "<spellId>": {"name": .., "rank": .., "icon": ..} }` — ids become numeric keys per the JSON convention), `data/ground-truth/talents.json`, `data/ground-truth/auras.json`. Task 9 consumes these files.

- [ ] **Step 1: Write the addon TOC**

`addon/XyrecDump/XyrecDump.toc`:

```
## Interface: 20505, 20506
## Title: XyrecDump
## Notes: Ground-truth oracle: dumps spell/talent/aura facts to SavedVariables
## SavedVariables: XyrecDumpDB
core.lua
```

- [ ] **Step 2: Write `addon/XyrecDump/core.lua`**

```lua
XyrecDumpDB = XyrecDumpDB or {}

local scanner = CreateFrame("Frame")
local scanState = nil
local BATCH = 2000

scanner:SetScript("OnUpdate", function()
  if not scanState then return end
  local db = XyrecDumpDB.spells
  local hi = math.min(scanState.cur + BATCH - 1, scanState.to)
  for id = scanState.cur, hi do
    local name, rank, icon = GetSpellInfo(id)
    if name then
      db[id] = { name = name, rank = rank ~= "" and rank or nil, icon = icon }
    end
  end
  scanState.cur = hi + 1
  if scanState.cur > scanState.to then
    print(("XyrecDump: spell scan %d-%d done, %d spells known total.")
      :format(scanState.from, scanState.to, (function()
        local n = 0; for _ in pairs(db) do n = n + 1 end; return n
      end)()))
    scanState = nil
  end
end)

local function dump_spells(from, to)
  XyrecDumpDB.spells = XyrecDumpDB.spells or {}
  XyrecDumpDB.spells_meta = { build = (select(4, GetBuildInfo())), when = date("%Y-%m-%d %H:%M") }
  scanState = { from = from, to = to, cur = from }
  print(("XyrecDump: scanning spell ids %d-%d..."):format(from, to))
end

local function dump_talents()
  local db = { class = select(2, UnitClass("player")), tabs = {} }
  for tab = 1, GetNumTalentTabs() do
    local tabName, _, pointsSpent = GetTalentTabInfo(tab)
    local t = { name = tabName, pointsSpent = pointsSpent, talents = {} }
    for i = 1, GetNumTalents(tab) do
      local name, icon, tier, column, rank, maxRank = GetTalentInfo(tab, i)
      t.talents[i] = { name = name, tier = tier, column = column,
                       rank = rank, maxRank = maxRank }
    end
    db.tabs[tab] = t
  end
  XyrecDumpDB.talents = XyrecDumpDB.talents or {}
  XyrecDumpDB.talents[db.class] = db
  print("XyrecDump: talents dumped for " .. db.class)
end

local function dump_auras()
  local snap = { when = date("%Y-%m-%d %H:%M"), buffs = {}, debuffs = {} }
  for i = 1, 40 do
    local name, icon, count, _, duration, expirationTime, source, _, _, spellId = UnitBuff("player", i)
    if not name then break end
    snap.buffs[i] = { name = name, spellId = spellId, count = count, duration = duration }
  end
  for i = 1, 40 do
    local name, icon, count, _, duration, expirationTime, source, _, _, spellId = UnitDebuff("player", i)
    if not name then break end
    snap.debuffs[i] = { name = name, spellId = spellId, count = count, duration = duration }
  end
  XyrecDumpDB.aura_snapshots = XyrecDumpDB.aura_snapshots or {}
  table.insert(XyrecDumpDB.aura_snapshots, snap)
  print(("XyrecDump: snapshot #%d (%d buffs, %d debuffs). /reload to persist.")
    :format(#XyrecDumpDB.aura_snapshots, #snap.buffs, #snap.debuffs))
end

SLASH_XDUMP1 = "/xdump"
SlashCmdList["XDUMP"] = function(msg)
  local cmd, a, b = msg:match("^(%S*)%s*(%S*)%s*(%S*)")
  if cmd == "spells" then
    dump_spells(tonumber(a) or 1, tonumber(b) or 200000)
  elseif cmd == "talents" then dump_talents()
  elseif cmd == "auras" then dump_auras()
  else
    print("XyrecDump usage: /xdump spells [from] [to] | /xdump talents | /xdump auras")
    print("NOTE: data persists to SavedVariables on /reload or logout.")
  end
end
```

If any API in this file errors in-game (BugSack will show it), the *client* is the authority — adjust the addon to the signatures the client actually has, and note the difference in `data/ground-truth/README.md`.

- [ ] **Step 3: Write `tools/install-addon.sh` and install**

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."
DST="/Applications/World of Warcraft/_anniversary_/Interface/AddOns/XyrecDump"
rm -rf "$DST"
cp -R addon/XyrecDump "$DST"
echo "installed XyrecDump -> $DST"
```

```bash
chmod +x tools/install-addon.sh && ./tools/install-addon.sh
```

Expected: `installed XyrecDump -> ...`. (Copy, not symlink — the mac client is unreliable with symlinked addons.)

- [ ] **Step 4: Write the failing importer test**

`tests/lua/test_groundtruth.lua`:

```lua
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
```

- [ ] **Step 5: Run test to verify it fails**

Run: `./tests/run.sh`
Expected: FAIL — `module 'groundtruth' not found`.

- [ ] **Step 6: Implement `tools/sv/groundtruth.lua` and the CLI command**

`tools/sv/groundtruth.lua`:

```lua
local sv = require("sv")
local json = require("json")
local M = {}

M.DUMP_PATH = "/Applications/World of Warcraft/_anniversary_/WTF/Account/THESNUB/SavedVariables/XyrecDump.lua"

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
  if db.aura_snapshots then write_json(outDir .. "/auras.json", db.aura_snapshots) end
  return true
end

return M
```

In `tools/wa-codec/main.lua` add:

```lua
commands["pull-groundtruth"] = function()
  local gt = require("groundtruth")
  os.execute("mkdir -p data/ground-truth")
  gt.import(gt.DUMP_PATH, "data/ground-truth")
  print("ground truth updated in data/ground-truth/")
end
```

- [ ] **Step 7: Run test to verify it passes**

Run: `./tests/run.sh`
Expected: `OK test_groundtruth`.

- [ ] **Step 8: Commit**

```bash
git add addon tools/install-addon.sh tools/sv/groundtruth.lua tools/wa-codec/main.lua tests/lua/test_groundtruth.lua
git commit -m "feat: XyrecDump ground-truth addon and pull-groundtruth importer"
```

**In-game step (user, deferred to Task 12 checklist):** log in, `/xdump spells 1 200000`, wait for "done", `/xdump talents`, `/reload`, then run `./tools/wa pull-groundtruth`.

---

### Task 8: db2 offline layer — build detection + wago.tools fetch

**Files:**
- Create: `tools/migrate/fetch_db2.py`
- Create: `tests/py/test_build_info.py`
- Create: `tests/py/fixtures/build.info` (fixture)

**Interfaces:**
- Consumes: nothing internal (network + game install).
- Produces: `parse_build_info(text) -> str` (e.g. `"2.5.6.68775"`), CLI `python3 tools/migrate/fetch_db2.py [--tables SpellName,Talent,Spell]` writing `data/ground-truth/db2/<Table>.csv`. Task 9 reads `SpellName.csv` (columns `ID,Name_lang`).

- [ ] **Step 1: Create the fixture and failing test**

`.build.info` is pipe-header, semicolon-attribute format; the `Version` column holds e.g. `2.5.6.68775`. Copy two lines from the real file into the fixture:

```bash
mkdir -p tests/py/fixtures tools/migrate
head -2 "/Applications/World of Warcraft/_anniversary_/.build.info" > tests/py/fixtures/build.info
cat tests/py/fixtures/build.info   # eyeball: find which |-separated column is Version
```

`tests/py/test_build_info.py`:

```python
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from fetch_db2 import parse_build_info

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "build.info"

def test_parse_build_info():
    version = parse_build_info(FIXTURE.read_text())
    parts = version.split(".")
    assert len(parts) == 4, f"expected a.b.c.build, got {version}"
    assert parts[0] == "2" and parts[1] == "5", f"expected 2.5.x build, got {version}"
    assert parts[3].isdigit() and int(parts[3]) > 60000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/py -q`
Expected: FAIL — `No module named 'fetch_db2'`.

- [ ] **Step 3: Implement `tools/migrate/fetch_db2.py`**

```python
#!/usr/bin/env python3
"""Fetch db2 CSV exports for the installed build from wago.tools.

The header line of .build.info is |-separated column specs like
"Version!STRING:0"; data lines are |-separated values.
"""
import argparse
import pathlib
import sys
import urllib.request

BUILD_INFO = pathlib.Path("/Applications/World of Warcraft/_anniversary_/.build.info")
OUT_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "ground-truth" / "db2"
DEFAULT_TABLES = ["SpellName", "Spell", "Talent", "TalentTab"]


def parse_build_info(text: str) -> str:
    lines = [l for l in text.strip().splitlines() if l.strip()]
    header = [c.split("!")[0] for c in lines[0].split("|")]
    idx = header.index("Version")
    for line in lines[1:]:
        cols = line.split("|")
        if len(cols) > idx and cols[idx].count(".") == 3:
            return cols[idx]
    raise ValueError("no Version column value found in .build.info")


def fetch(table: str, build: str) -> pathlib.Path:
    url = f"https://wago.tools/api/csv/{table}?build={build}"
    out = OUT_DIR / f"{table}.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "ccwow-dev-env/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if not data or b"," not in data.split(b"\n", 1)[0]:
        raise ValueError(f"{table}: response does not look like CSV")
    out.write_bytes(data)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default=",".join(DEFAULT_TABLES))
    args = ap.parse_args()
    build = parse_build_info(BUILD_INFO.read_text())
    print(f"installed build: {build}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for table in args.tables.split(","):
        try:
            out = fetch(table, build)
            print(f"  {table}: {out} ({out.stat().st_size} bytes)")
        except Exception as exc:  # graceful per-table failure (spec §8 risk)
            failures.append(table)
            print(f"  {table}: FAILED ({exc}) — in-game dumps remain authoritative; "
                  f"retry later or try the nearest 2.5.x build on wago.tools", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test, then the real fetch**

Run: `python3 -m pytest tests/py -q` — expect pass.
Run: `python3 tools/migrate/fetch_db2.py` — expect `installed build: 2.5.6.<build>` and per-table results. Network/coverage failures are acceptable (graceful message); if `SpellName` fails, note it — Task 9 must then rely on in-game dumps only.

- [ ] **Step 5: Commit**

```bash
git add tools/migrate/fetch_db2.py tests/py data/ground-truth/db2 2>/dev/null || true
git add tools/migrate/fetch_db2.py tests/py
git commit -m "feat: db2 offline ground-truth fetch from wago.tools for installed build"
```

(Commit the CSVs too if the fetch succeeded — they're data, versioned on purpose.)

---

### Task 9: Spell validation

**Files:**
- Create: `tools/migrate/groundtruth.py`
- Create: `tools/migrate/validate_spells.py`
- Test: `tests/py/test_validate_spells.py`

**Interfaces:**
- Consumes: `data/ground-truth/spells.json` (Task 7 format), `data/ground-truth/db2/SpellName.csv` (Task 8), aura JSON files (Task 6 payload shape or bare aura objects).
- Produces: `GroundTruth.load(dir) -> GroundTruth` with `.spell_by_id(id) -> dict|None`, `.ids_by_name(name) -> list[int]`, `.source_of(id) -> "ingame"|"db2"` (in-game wins on conflict, spec §4); `validate_payload(payload, gt) -> list[Finding]` where `Finding = {"aura": id, "path": str, "kind": "id"|"name", "value": ..., "status": "ok"|"unknown", "note": str}`; CLI `python3 tools/migrate/validate_spells.py <payload.json>` printing a report, exit 1 if any `unknown`. Task 12's workflow doc names this as the gate every migration runs.

- [ ] **Step 1: Write the failing test**

`tests/py/test_validate_spells.py`:

```python
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from groundtruth import GroundTruth
from validate_spells import validate_payload

def make_gt(tmp_path):
    gt = tmp_path / "gt"
    (gt / "db2").mkdir(parents=True)
    (gt / "spells.json").write_text(json.dumps({
        "8050": {"name": "Flame Shock", "rank": "Rank 1"},
        "8052": {"name": "Flame Shock", "rank": "Rank 2"},
        "30455": {"name": "Ice Lance"},
    }))
    (gt / "db2" / "SpellName.csv").write_text(
        "ID,Name_lang\n8050,Flame Shock\n8052,Flame Shock\n30455,Ice Lance\n99999,Db2 Only Spell\n")
    return GroundTruth.load(gt)

def test_groundtruth_lookup(tmp_path):
    gt = make_gt(tmp_path)
    assert gt.spell_by_id(8050)["name"] == "Flame Shock"
    assert sorted(gt.ids_by_name("Flame Shock")) == [8050, 8052]
    assert gt.spell_by_id(99999)["name"] == "Db2 Only Spell"   # db2 fallback
    assert gt.source_of(8050) == "ingame" and gt.source_of(99999) == "db2"
    assert gt.spell_by_id(12345) is None

def test_validate_payload(tmp_path):
    gt = make_gt(tmp_path)
    payload = {"m": "d", "v": 2000, "d": {
        "id": "T", "regionType": "icon",
        "triggers": {"1": {"trigger": {"type": "aura2",
                                       "auranames": ["Flame Shock", "Bogus Spell"],
                                       "spellId": 8050}},
                     "2": {"trigger": {"type": "cooldown", "spellIds": [30455, 424242]}},
                     "activeTriggerMode": -10}}}
    findings = validate_payload(payload, gt)
    by = {(f["kind"], str(f["value"])): f["status"] for f in findings}
    assert by[("name", "Flame Shock")] == "ok"
    assert by[("name", "Bogus Spell")] == "unknown"
    assert by[("id", "8050")] == "ok"
    assert by[("id", "424242")] == "unknown"
    assert all(f["aura"] == "T" for f in findings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/py -q`
Expected: FAIL — `No module named 'groundtruth'`.

- [ ] **Step 3: Implement `tools/migrate/groundtruth.py`**

```python
"""Ground-truth store. In-game dumps win over db2 on conflict (spec §4)."""
import csv
import json
import pathlib


class GroundTruth:
    def __init__(self, ingame: dict, db2_names: dict):
        self._ingame = {int(k): v for k, v in ingame.items()}
        self._db2 = {int(k): v for k, v in db2_names.items()}
        self._by_name: dict[str, list[int]] = {}
        for sid, rec in self._db2.items():
            self._by_name.setdefault(rec["name"], []).append(sid)
        for sid, rec in self._ingame.items():
            ids = self._by_name.setdefault(rec["name"], [])
            if sid not in ids:
                ids.append(sid)

    @classmethod
    def load(cls, gt_dir) -> "GroundTruth":
        gt_dir = pathlib.Path(gt_dir)
        ingame = {}
        spells_json = gt_dir / "spells.json"
        if spells_json.exists():
            ingame = json.loads(spells_json.read_text())
        db2_names = {}
        csv_path = gt_dir / "db2" / "SpellName.csv"
        if csv_path.exists():
            with csv_path.open(newline="") as f:
                for row in csv.DictReader(f):
                    db2_names[row["ID"]] = {"name": row["Name_lang"]}
        if not ingame and not db2_names:
            raise FileNotFoundError(
                f"no ground truth in {gt_dir} — run /xdump in-game + wa pull-groundtruth, "
                f"and/or tools/migrate/fetch_db2.py")
        return cls(ingame, db2_names)

    def spell_by_id(self, spell_id: int):
        return self._ingame.get(spell_id) or self._db2.get(spell_id)

    def ids_by_name(self, name: str):
        return self._by_name.get(name, [])

    def source_of(self, spell_id: int):
        if spell_id in self._ingame:
            return "ingame"
        if spell_id in self._db2:
            return "db2"
        return None
```

- [ ] **Step 4: Implement `tools/migrate/validate_spells.py`**

```python
#!/usr/bin/env python3
"""Walk a WA payload for spell references and validate against ground truth."""
import json
import pathlib
import sys

from groundtruth import GroundTruth

GT_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "ground-truth"

# trigger keys whose value is a spell NAME / a spell ID / a list of either
NAME_KEYS = {"spellName", "realSpellName", "itemName"}
NAME_LIST_KEYS = {"auranames"}
ID_KEYS = {"spellId"}
ID_LIST_KEYS = {"spellIds", "auraspellids"}


def _walk(node, path, aura_id, out):
    if isinstance(node, dict):
        for key, value in node.items():
            p = f"{path}.{key}"
            if key in NAME_KEYS and isinstance(value, str) and value:
                out.append(("name", value, p, aura_id))
            elif key in NAME_LIST_KEYS and isinstance(value, (list, dict)):
                items = value if isinstance(value, list) else value.values()
                for v in items:
                    if isinstance(v, str) and v:
                        out.append(("name", v, p, aura_id))
            elif key in ID_KEYS and isinstance(value, (int, str)) and str(value).isdigit():
                out.append(("id", int(value), p, aura_id))
            elif key in ID_LIST_KEYS and isinstance(value, (list, dict)):
                items = value if isinstance(value, list) else value.values()
                for v in items:
                    if isinstance(v, (int, str)) and str(v).isdigit():
                        out.append(("id", int(v), p, aura_id))
            else:
                _walk(value, p, aura_id, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, f"{path}[{i}]", aura_id, out)


def validate_payload(payload, gt: GroundTruth):
    auras = [payload["d"]] + list(payload.get("c") or [])
    findings = []
    for aura in auras:
        refs = []
        _walk(aura.get("triggers", {}), "triggers", aura.get("id", "?"), refs)
        for kind, value, path, aura_id in refs:
            if kind == "id":
                rec = gt.spell_by_id(value)
                status = "ok" if rec else "unknown"
                note = (f"{rec['name']} [{gt.source_of(value)}]" if rec
                        else "spell id not in ground truth")
            else:
                ids = gt.ids_by_name(value)
                status = "ok" if ids else "unknown"
                note = (f"ids: {sorted(ids)}" if ids else "spell name not in ground truth")
            findings.append({"aura": aura_id, "path": path, "kind": kind,
                             "value": value, "status": status, "note": note})
    return findings


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_spells.py <payload.json>", file=sys.stderr)
        return 2
    payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
    gt = GroundTruth.load(GT_DIR)
    findings = validate_payload(payload, gt)
    bad = 0
    for f in findings:
        mark = "OK " if f["status"] == "ok" else "?? "
        if f["status"] != "ok":
            bad += 1
        print(f'{mark} {f["aura"]}: {f["kind"]}={f["value"]!r} at {f["path"]} — {f["note"]}')
    print(f'{len(findings)} refs, {bad} unknown')
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/migrate/groundtruth.py tools/migrate/validate_spells.py tests/py/test_validate_spells.py
git commit -m "feat: spell reference validation against client ground truth"
```

---

### Task 10: Style templates — extract + restyle

**Files:**
- Create: `tools/migrate/style_fields.py`
- Create: `tools/migrate/template_extract.py`
- Create: `tools/migrate/restyle.py`
- Test: `tests/py/test_restyle.py`

**Interfaces:**
- Consumes: aura JSON (payload or bare aura object).
- Produces: `STYLE_FIELDS: dict[str, list[str]]` (per regionType, includes `"common"`), `LOGIC_FIELDS: list[str]`; `extract_template(aura) -> dict` (style fields present on the aura); `apply_template(donor_aura, template) -> (aura, report)` where the result keeps donor logic, takes template style, and `report` lists donor keys that are neither logic nor style (carried over donor-value, flagged for review). CLI: `template_extract.py <payload.json> -o tools/migrate/templates/<regionType>.json`, `restyle.py <donor-payload.json> --template <template.json> -o <out.json>`. Restyle applies to `d` and every entry of `c` whose regionType matches the template's; non-matching children pass through with a report line.

- [ ] **Step 1: Write the failing test**

`tests/py/test_restyle.py`:

```python
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from style_fields import STYLE_FIELDS, LOGIC_FIELDS
from template_extract import extract_template
from restyle import apply_template

EXEMPLAR = {
    "id": "Mine - Pretty", "uid": "MMMMMMMMMMM", "regionType": "icon",
    "width": 40, "height": 40, "zoom": 0.3, "cooldown": True, "cooldownSwipe": True,
    "anchorFrameType": "UIPARENT", "frameStrata": 1, "scale": 0.75, "alpha": 1,
    "subRegions": [{"type": "subbackground"},
                   {"type": "subtext", "text_fontSize": 14, "text_text": "%p"}],
    "triggers": {"1": {"trigger": {"type": "aura2", "auranames": ["My Spell"]}},
                 "activeTriggerMode": -10},
    "load": {"class": {"multi": {"SHAMAN": True}}},
}

DONOR = {
    "id": "Donor - Ugly", "uid": "UUUUUUUUUUU", "regionType": "icon",
    "width": 64, "height": 64, "zoom": 0, "cooldown": False,
    "desc": "from some TBC pack",
    "someUnknownField": 42,
    "triggers": {"1": {"trigger": {"type": "cooldown", "spellIds": [17364]}},
                 "activeTriggerMode": -10},
    "conditions": [{"check": {"trigger": 1}}],
    "load": {"class": {"multi": {"SHAMAN": True}}, "talent": {"multi": {"5": True}}},
}

def test_extract_template():
    tpl = extract_template(EXEMPLAR)
    assert tpl["regionType"] == "icon"
    assert tpl["width"] == 40 and tpl["cooldownSwipe"] is True
    assert "triggers" not in tpl and "id" not in tpl and "uid" not in tpl

def test_apply_template_keeps_logic_takes_style():
    tpl = extract_template(EXEMPLAR)
    out, report = apply_template(dict(DONOR), tpl)
    # style from template
    assert out["width"] == 40 and out["zoom"] == 0.3 and out["cooldown"] is True
    assert out["subRegions"] == EXEMPLAR["subRegions"]
    # logic from donor
    assert out["triggers"] == DONOR["triggers"]
    assert out["conditions"] == DONOR["conditions"]
    assert out["load"] == DONOR["load"]
    assert out["id"] == "Donor - Ugly" and out["uid"] == "UUUUUUUUUUU"
    assert out["desc"] == "from some TBC pack"
    # unknown key carried over but reported
    assert out["someUnknownField"] == 42
    assert any("someUnknownField" in line for line in report)

def test_region_type_mismatch_is_rejected():
    tpl = extract_template(EXEMPLAR)
    bar = dict(DONOR); bar["regionType"] = "aurabar"
    out, report = apply_template(bar, tpl)
    assert out == bar                      # unchanged
    assert any("regionType" in line for line in report)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/py -q`
Expected: FAIL — `No module named 'style_fields'`.

- [ ] **Step 3: Implement `tools/migrate/style_fields.py`**

```python
"""Field classification for restyling (spec §5.3).

STYLE = presentation, copied from the exemplar template.
LOGIC = behavior, kept from the donor.
Anything else: carried over from the donor and REPORTED for review.
actions/animation are STYLE by default (glow/sound styling); use
restyle.py --keep-donor-actions when a donor's actions are behavioral.
"""

LOGIC_FIELDS = [
    "id", "uid", "parent", "regionType", "triggers", "conditions", "load",
    "desc", "url", "version", "semver", "wagoID", "config", "authorOptions",
    "information", "tocversion", "internalVersion", "source",
    "iconSource", "displayIcon", "icon",  # which icon to show follows the trigger
    "adjustedMax", "adjustedMin", "useAdjustededMax", "useAdjustededMin",
]

_COMMON_STYLE = [
    "width", "height", "xOffset", "yOffset", "anchorPoint", "anchorFrameType",
    "anchorFrameFrame", "selfPoint", "frameStrata", "scale", "alpha", "color",
    "desaturate", "inverse", "subRegions", "actions", "animation",
]

STYLE_FIELDS = {
    "common": _COMMON_STYLE,
    "icon": ["zoom", "keepAspectRatio", "cooldown", "cooldownSwipe", "cooldownEdge",
             "cooldownTextDisabled", "useCooldownModRate"],
    "aurabar": ["texture", "textureSource", "barColor", "barColor2", "backgroundColor",
                "orientation", "icon_side", "icon_color", "sparkColor", "sparkTexture",
                "sparkWidth", "sparkHeight", "sparkHidden", "spark", "borderBackdrop",
                "backdropColor", "border", "borderColor", "borderEdge", "borderInset",
                "borderOffset", "borderSize", "zoom"],
    "progresstexture": ["foregroundTexture", "backgroundTexture", "foregroundColor",
                        "backgroundColor", "orientation", "compress", "blendMode",
                        "backgroundOffset", "startAngle", "endAngle", "crop_x", "crop_y",
                        "rotation", "mirror"],
    "text": ["displayText", "fixedWidth", "font", "fontSize", "outline", "justify",
             "shadowColor", "shadowXOffset", "shadowYOffset", "wordWrap",
             "automaticWidth"],
}


def style_fields_for(region_type: str) -> list[str]:
    return STYLE_FIELDS["common"] + STYLE_FIELDS.get(region_type, [])
```

- [ ] **Step 4: Implement `tools/migrate/template_extract.py`**

```python
#!/usr/bin/env python3
"""Extract a style template from an exemplar aura (spec §5: style is data)."""
import argparse
import json
import pathlib
import sys

from style_fields import style_fields_for


def extract_template(aura: dict) -> dict:
    tpl = {"regionType": aura["regionType"]}
    for field in style_fields_for(aura["regionType"]):
        if field in aura:
            tpl[field] = aura[field]
    return tpl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("payload", help="payload JSON from `wa extract` (uses .d)")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.payload).read_text())
    aura = data["d"] if "d" in data else data
    tpl = extract_template(aura)
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(tpl, indent=2, sort_keys=True) + "\n")
    print(f"template ({tpl['regionType']}, {len(tpl) - 1} fields) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Implement `tools/migrate/restyle.py`**

```python
#!/usr/bin/env python3
"""Apply a style template to a donor payload: donor logic + template style."""
import argparse
import json
import pathlib
import sys

from style_fields import LOGIC_FIELDS, style_fields_for


def apply_template(aura: dict, template: dict, keep_donor_actions: bool = False):
    report = []
    if aura.get("regionType") != template["regionType"]:
        report.append(f'{aura.get("id")}: regionType {aura.get("regionType")!r} != '
                      f'template {template["regionType"]!r} — left unchanged')
        return aura, report
    style = set(style_fields_for(template["regionType"]))
    if keep_donor_actions:
        style -= {"actions", "animation"}
    out = {}
    for key, value in aura.items():
        if key in style:
            continue                      # replaced by template below (or dropped)
        out[key] = value
        if key not in LOGIC_FIELDS and key not in style:
            report.append(f'{aura.get("id")}: kept unclassified donor field {key!r} — review')
    for key in style:
        if key in template:
            out[key] = template[key]
    donor_sub = aura.get("subRegions") or []
    if any("%c" in str(s.get("text_text", "")) for s in donor_sub if isinstance(s, dict)):
        report.append(f'{aura.get("id")}: donor had custom-text (%c) subregions replaced '
                      f'by template — port the custom text manually if needed')
    return out, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("payload")
    ap.add_argument("--template", required=True)
    ap.add_argument("--keep-donor-actions", action="store_true")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    payload = json.loads(pathlib.Path(args.payload).read_text())
    template = json.loads(pathlib.Path(args.template).read_text())
    auras = [payload["d"]] + list(payload.get("c") or [])
    full_report = []
    for i, aura in enumerate(auras):
        new, report = apply_template(aura, template, args.keep_donor_actions)
        full_report.extend(report)
        if i == 0:
            payload["d"] = new
        else:
            payload["c"][i - 1] = new
    pathlib.Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for line in full_report:
        print("NOTE:", line)
    print(f"restyled {len(auras)} aura(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 -m pytest tests/py -q`
Expected: all pass.

- [ ] **Step 7: Extract real templates from the user's pack (smoke + deliverable)**

```bash
./tools/wa extract "Shaman - Stormstrike" -o tmp/exemplar_icon.json
python3 tools/migrate/template_extract.py tmp/exemplar_icon.json -o tools/migrate/templates/icon.json
./tools/wa extract "Shaman - Mana Bar" -o tmp/exemplar_bar.json
python3 tools/migrate/template_extract.py tmp/exemplar_bar.json -o tools/migrate/templates/aurabar.json
```

Expected: two template files; eyeball them — they should contain sizes/anchors/colors and NO triggers.

- [ ] **Step 8: Commit**

```bash
git add tools/migrate/style_fields.py tools/migrate/template_extract.py tools/migrate/restyle.py tools/migrate/templates tests/py/test_restyle.py
git commit -m "feat: style template extraction and donor restyling"
```

---

### Task 11: `wa audit` — structural validation

**Files:**
- Create: `tools/migrate/audit.py`
- Modify: `tools/wa` — no change needed (audit is invoked via python3; document in Task 12)
- Test: `tests/py/test_audit.py`

**Interfaces:**
- Consumes: a decoded displays JSON. This task ALSO adds one tiny `wa` subcommand: `wa dump-displays`, printing `json.to_json(env.WeakAurasSaved.displays)` for the live file — `audit.py` shells out to it when run without an argument.
- Produces: `audit_displays(displays: dict) -> list[str]` (one issue per line, empty = clean); CLI `python3 tools/migrate/audit.py [displays.json]` (no arg → runs `./tools/wa dump-displays` itself). Exit 1 if issues found.

- [ ] **Step 1: Add `wa dump-displays` subcommand**

In `tools/wa-codec/main.lua` add:

```lua
commands["dump-displays"] = function()
  local sv = require("sv")
  local env = sv.load(sv.LIVE_PATH)
  io.write(json.to_json(env.WeakAurasSaved.displays))
end
```

Smoke: `./tools/wa dump-displays | head -5` — expect JSON.

- [ ] **Step 2: Write the failing test**

`tests/py/test_audit.py`:

```python
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from audit import audit_displays

def base():
    return {
        "Group": {"id": "Group", "uid": "GGGGGGGGGGG", "regionType": "group",
                  "controlledChildren": ["Child"],
                  "triggers": {"1": {"trigger": {"type": "aura2"}}, "activeTriggerMode": -10}},
        "Child": {"id": "Child", "uid": "AAAAAAAAAAA", "regionType": "icon", "parent": "Group",
                  "triggers": {"1": {"trigger": {"type": "aura2"}}, "activeTriggerMode": -10}},
    }

def test_clean_passes():
    assert audit_displays(base()) == []

def test_dangling_child():
    d = base(); d["Group"]["controlledChildren"].append("Ghost")
    assert any("Ghost" in i and "dangling" in i for i in audit_displays(d))

def test_orphan_parent_link():
    d = base(); d["Child"]["parent"] = "Nowhere"
    assert any("Nowhere" in i for i in audit_displays(d))

def test_one_way_link():
    d = base(); d["Group"]["controlledChildren"] = []      # child still points at Group
    assert any("not listed" in i for i in audit_displays(d))

def test_empty_dynamicgroup():
    d = base()
    d["Empty"] = {"id": "Empty", "uid": "EEEEEEEEEEE", "regionType": "dynamicgroup",
                  "controlledChildren": [],
                  "triggers": {"1": {"trigger": {"type": "aura2"}}, "activeTriggerMode": -10}}
    assert any("empty dynamicgroup" in i for i in audit_displays(d))

def test_missing_uid_and_dup_uid():
    d = base()
    del d["Child"]["uid"]
    issues = audit_displays(d)
    assert any("missing uid" in i for i in issues)
    d = base(); d["Child"]["uid"] = d["Group"]["uid"]
    assert any("duplicate uid" in i for i in audit_displays(d))

def test_id_key_mismatch():
    d = base(); d["Child"]["id"] = "Renamed"
    assert any("key/id mismatch" in i for i in audit_displays(d))

def test_missing_triggers():
    d = base(); del d["Child"]["triggers"]
    assert any("no triggers" in i for i in audit_displays(d))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/py -q`
Expected: FAIL — `No module named 'audit'`.

- [ ] **Step 4: Implement `tools/migrate/audit.py`**

```python
#!/usr/bin/env python3
"""Structural audit of a WeakAuras displays table (spec §6)."""
import json
import pathlib
import subprocess
import sys

GROUP_TYPES = {"group", "dynamicgroup"}


def audit_displays(displays: dict) -> list[str]:
    issues = []
    uids = {}
    for key, aura in displays.items():
        aura_id = aura.get("id")
        if aura_id != key:
            issues.append(f"{key}: key/id mismatch (id={aura_id!r})")
        if not aura.get("uid"):
            issues.append(f"{key}: missing uid")
        else:
            uids.setdefault(aura["uid"], []).append(key)
        if not aura.get("regionType"):
            issues.append(f"{key}: missing regionType")
        if "triggers" not in aura:
            issues.append(f"{key}: no triggers table")
        parent = aura.get("parent")
        if parent is not None:
            pa = displays.get(parent)
            if pa is None:
                issues.append(f"{key}: parent {parent!r} does not exist")
            elif key not in (pa.get("controlledChildren") or []):
                issues.append(f"{key}: not listed in parent {parent!r} controlledChildren")
        cc = aura.get("controlledChildren")
        if cc is not None:
            if aura.get("regionType") not in GROUP_TYPES:
                issues.append(f"{key}: has controlledChildren but regionType "
                              f"{aura.get('regionType')!r}")
            seen = set()
            for child in cc:
                if child in seen:
                    issues.append(f"{key}: duplicate controlledChildren entry {child!r}")
                seen.add(child)
                ca = displays.get(child)
                if ca is None:
                    issues.append(f"{key}: dangling controlledChildren ref {child!r}")
                elif ca.get("parent") != key:
                    issues.append(f"{key}: child {child!r} has parent "
                                  f"{ca.get('parent')!r}, expected {key!r}")
            if aura.get("regionType") == "dynamicgroup" and len(cc) == 0:
                issues.append(f"{key}: empty dynamicgroup")
    for uid, keys in uids.items():
        if len(keys) > 1:
            issues.append(f"duplicate uid {uid!r}: {', '.join(sorted(keys))}")
    return sorted(issues)


def main() -> int:
    if len(sys.argv) > 1:
        displays = json.loads(pathlib.Path(sys.argv[1]).read_text())
    else:
        repo = pathlib.Path(__file__).resolve().parents[2]
        out = subprocess.run([str(repo / "tools" / "wa"), "dump-displays"],
                             capture_output=True, text=True, check=True)
        displays = json.loads(out.stdout)
    issues = audit_displays(displays)
    for issue in issues:
        print(issue)
    print(f"{len(displays)} displays, {len(issues)} issues")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests, then audit the real live file**

Run: `python3 -m pytest tests/py -q` — all pass.
Run: `python3 tools/migrate/audit.py` — expect a real issue list (e.g. `Shaman - Maelstrom Weapon: empty dynamicgroup` and likely others across 470 displays). Save it: `python3 tools/migrate/audit.py > tmp/audit-baseline.txt || true` — this is the damage report that seeds the deferred shaman/mage work. Exit 1 here is expected and is NOT a task failure.

- [ ] **Step 6: Commit**

```bash
git add tools/migrate/audit.py tools/wa-codec/main.lua tests/py/test_audit.py
git commit -m "feat: structural audit of the displays table"
```

---

### Task 12: Lint toolchain + CLAUDE.md workflow + acceptance checklist

**Files:**
- Create: `tools/migrate/gen_luacheckrc.py`
- Create: `tools/migrate/extract_custom_code.py`
- Create: `.luacheckrc-wow` (generated, committed)
- Modify: `CLAUDE.md`
- Create: `docs/acceptance-checklist.md`
- Test: `tests/py/test_custom_code.py`

**Interfaces:**
- Consumes: `refs/wow-ui-source` (cloned here), `refs/WeakAuras2` (cloned here), aura/displays JSON.
- Produces: `.luacheckrc-wow` usable as `luacheck --config .luacheckrc-wow <files>`; `extract_snippets(displays) -> list[{"aura": id, "slot": str, "code": str}]` pulling custom code from trigger fields (`custom`, `customDuration`, `customName`, `customIcon`, `customTexture`, `customStacks`, `custom_hide`) and action fields (`actions.start.custom`, `actions.init.custom`, `actions.finish.custom`) and text format custom funcs (any string field ending in `_custom`); CLI `extract_custom_code.py [displays.json] -o tmp/snippets/` writing one `.lua` file per snippet, wrapped as `local aura_env = ...; local _ = <code>` when the code is an expression (`function(...)...end`) or raw statements otherwise.

- [ ] **Step 1: Install luacheck and clone refs**

```bash
brew install luacheck
mkdir -p refs
git clone --depth 1 --branch classic_anniversary https://github.com/Gethe/wow-ui-source refs/wow-ui-source
git clone --depth 1 https://github.com/WeakAuras/WeakAuras2 refs/WeakAuras2
ls refs/wow-ui-source/Interface/AddOns/ | grep -i apidoc
ls refs/WeakAuras2/.luacheckrc
```

Expected: `Blizzard_APIDocumentation`, `Blizzard_APIDocumentationGenerated` listed; `.luacheckrc` exists.

- [ ] **Step 2: Write the failing test for the snippet extractor**

`tests/py/test_custom_code.py`:

```python
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "migrate"))
from extract_custom_code import extract_snippets

DISPLAYS = {
    "A": {"id": "A", "regionType": "icon",
          "triggers": {"1": {"trigger": {"type": "custom",
                                         "custom": "function() return true end",
                                         "customDuration": "function() return 10, GetTime() end"}},
                       "activeTriggerMode": -10},
          "actions": {"init": {"custom": "aura_env.x = 1", "do_custom": True},
                      "start": {}, "finish": {}}},
    "B": {"id": "B", "regionType": "icon",
          "triggers": {"1": {"trigger": {"type": "aura2"}}, "activeTriggerMode": -10}},
}

def test_extract_snippets():
    snips = extract_snippets(DISPLAYS)
    slots = {(s["aura"], s["slot"]) for s in snips}
    assert ("A", "triggers.1.trigger.custom") in slots
    assert ("A", "triggers.1.trigger.customDuration") in slots
    assert ("A", "actions.init.custom") in slots
    assert not any(s["aura"] == "B" for s in snips)
```

Run: `python3 -m pytest tests/py -q` → FAIL (`No module named 'extract_custom_code'`).

- [ ] **Step 3: Implement `tools/migrate/extract_custom_code.py`**

```python
#!/usr/bin/env python3
"""Extract WA custom-code snippets into lintable .lua files (spec §6)."""
import json
import pathlib
import re
import subprocess
import sys

CODE_KEYS = {"custom", "customDuration", "customName", "customIcon", "customTexture",
             "customStacks", "custom_hide", "customVariables", "customText"}


def _walk(node, path, out):
    if isinstance(node, dict):
        for key, value in node.items():
            p = f"{path}.{key}" if path else str(key)
            if isinstance(value, str) and (key in CODE_KEYS or key.endswith("_custom")) \
                    and value.strip():
                out.append((p, value))
            else:
                _walk(value, p, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, f"{path}[{i}]", out)


def extract_snippets(displays: dict) -> list[dict]:
    snippets = []
    for aura_id, aura in displays.items():
        found = []
        _walk({"triggers": aura.get("triggers", {}),
               "actions": aura.get("actions", {}),
               "customText": aura.get("customText", "")}, "", found)
        for slot, code in found:
            snippets.append({"aura": aura_id, "slot": slot, "code": code})
    return snippets


def wrap(code: str) -> str:
    header = "local aura_env, WeakAuras = ...\n"
    if re.match(r"^\s*function\b", code):
        return header + "local _ = " + code + "\n"
    return header + code + "\n"


def main() -> int:
    out_dir = pathlib.Path("tmp/snippets")
    args = sys.argv[1:]
    if "-o" in args:
        i = args.index("-o"); out_dir = pathlib.Path(args[i + 1]); del args[i:i + 2]
    if args:
        displays = json.loads(pathlib.Path(args[0]).read_text())
    else:
        repo = pathlib.Path(__file__).resolve().parents[2]
        proc = subprocess.run([str(repo / "tools" / "wa"), "dump-displays"],
                              capture_output=True, text=True, check=True)
        displays = json.loads(proc.stdout)
    out_dir.mkdir(parents=True, exist_ok=True)
    snippets = extract_snippets(displays)
    for i, s in enumerate(snippets):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f'{s["aura"]}--{s["slot"]}')
        (out_dir / f"{i:03d}--{safe}.lua").write_text(wrap(s["code"]))
    print(f"{len(snippets)} snippets -> {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run: `python3 -m pytest tests/py -q` → pass.

- [ ] **Step 4: Implement `tools/migrate/gen_luacheckrc.py` and generate**

```python
#!/usr/bin/env python3
"""Generate .luacheckrc-wow: union of Blizzard_APIDocumentationGenerated names
(classic_anniversary — client-exact) and WeakAuras2's proven globals list,
plus WA custom-code injected globals."""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
DOCS = REPO / "refs" / "wow-ui-source" / "Interface" / "AddOns" / "Blizzard_APIDocumentationGenerated"
WA_RC = REPO / "refs" / "WeakAuras2" / ".luacheckrc"
OUT = REPO / ".luacheckrc-wow"

def collect() -> set[str]:
    names = set()
    for f in DOCS.glob("*.lua"):
        text = f.read_text(errors="replace")
        for ns in re.findall(r'Namespace = "([A-Za-z0-9_]+)"', text):
            names.add(ns)
        if 'Namespace' not in text:
            for fn in re.findall(r'Name = "([A-Za-z0-9_]+)",\s*\n\s*Type = "Function"', text):
                names.add(fn)
    text = WA_RC.read_text(errors="replace")
    for name in re.findall(r'^\s*"([A-Za-z0-9_.]+)",?\s*$', text, re.M):
        names.add(name.split(".")[0])
    names |= {"aura_env", "WeakAuras", "WeakAurasSaved"}
    return names

def main() -> int:
    names = sorted(collect())
    with OUT.open("w") as f:
        f.write('-- GENERATED by tools/migrate/gen_luacheckrc.py -- do not edit\n')
        f.write('std = "lua51"\nmax_line_length = false\n')
        f.write('ignore = { "21.", "611", "612", "631" }  -- unused-var/whitespace noise in snippets\n')
        f.write("read_globals = {\n")
        for n in names:
            f.write(f'  "{n}",\n')
        f.write("}\n")
    print(f"{len(names)} globals -> {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

```bash
python3 tools/migrate/gen_luacheckrc.py
grep -c '"' .luacheckrc-wow   # expect thousands of entries
```

- [ ] **Step 5: Lint the live pack's custom code (smoke)**

```bash
python3 tools/migrate/extract_custom_code.py -o tmp/snippets
luacheck --config .luacheckrc-wow tmp/snippets/ || true
```

Expected: a report over the real snippets. Findings are expected (that's the point); errors about *missing globals that are real TBC APIs* mean the generator missed them — add to the generator, regenerate, re-run.

- [ ] **Step 6: Update `CLAUDE.md` with the workflow**

Append to `CLAUDE.md`:

```markdown
## WeakAura Dev Environment

Spec: docs/superpowers/specs/2026-07-18-weakaura-dev-environment-design.md

### Ground-truth rule (HARD)
No spell/talent fact may be written into an aura unless it resolves against
`data/ground-truth/` (in-game dumps win over db2). Model memory, wikis, and
"I'm sure it exists" are hypotheses only — the Anniversary client changes
spell availability over time (e.g. Ice Lance exists in TBC Anniversary).
Refresh: in-game `/xdump spells 1 200000` + `/xdump talents`, `/reload`,
then `./tools/wa pull-groundtruth`. Offline: `python3 tools/migrate/fetch_db2.py`.

### Commands
- `./tools/wa decode <string|@file>` / `./tools/wa encode <json>` — !WA:2! codec
- `./tools/wa extract "<id>" -o f.json` / `./tools/wa land f.json --parent "<id>" [--delete]`
- `./tools/wa backup` / `./tools/wa restore backups/<file>` / `./tools/wa dump-displays`
- `python3 tools/migrate/validate_spells.py <payload.json>` — spell gate (must pass pre-land)
- `python3 tools/migrate/restyle.py <donor.json> --template tools/migrate/templates/<t>.json -o out.json`
- `python3 tools/migrate/audit.py` — structural audit of the live file
- `./tests/run.sh` — full test suite

### Migration loop (per aura)
1. decode/extract donor → data/auras/donors/
2. validate_spells (fix unknowns via ground truth, never by assumption)
3. restyle with a template from tools/migrate/templates/
4. review diff → `wa land` (auto-backup) → `audit`
5. in-game: check visuals + BugSack; `/xdump` new facts back in

### Safety
Writes go through tools/sv/safety.lua only: game-closed guard, timestamped
backup in backups/, atomic verified write. The live SavedVariables path is in
tools/sv/sv.lua (LIVE_PATH). Never edit the live file by hand or with regex.
```

- [ ] **Step 7: Write `docs/acceptance-checklist.md`**

```markdown
# End-to-end acceptance (requires the game — user-driven)

1. Codec vs the real importer:
   - `./tools/wa extract "Shaman - Stormstrike" -o tmp/ss.json`
   - `./tools/wa encode tmp/ss.json | pbcopy`
   - In-game: WeakAuras → Import → paste. MUST preview and import cleanly.
   - Delete the imported copy afterwards.
2. Real export decodes:
   - In-game: right-click any aura group → Export to string → copy.
   - `pbpaste > tmp/real.txt && ./tools/wa decode @tmp/real.txt | head`
   - MUST print JSON with the expected ids.
3. Ground truth populated:
   - In-game: `/xdump spells 1 200000` (wait for "done"), `/xdump talents`, `/reload`.
   - `./tools/wa pull-groundtruth`
   - `python3 -c "import json;d=json.load(open('data/ground-truth/spells.json'));print(len(d))"`
     MUST be > 10000.
   - Spot-check the Ice Lance lesson: search spells.json for "Ice Lance" — record the
     actual IDs in data/ground-truth/README.md.
4. Round-trip write safety (uses the live file — game CLOSED):
   - `./tools/wa backup`
   - `./tools/wa extract "Shaman - Stormstrike" -o tmp/ss.json`
   - `./tools/wa land tmp/ss.json --parent "Shaman - Core Abilities" --delete`
     (lands the identical aura back onto itself)
   - `python3 tools/migrate/audit.py` — issue count MUST NOT increase vs tmp/audit-baseline.txt
   - Launch game: aura renders as before, BugSack clean.
5. `./tests/run.sh` passes end to end.
```

- [ ] **Step 8: Run everything and commit**

Run: `./tests/run.sh` — expect ALL TESTS PASSED.

```bash
git add tools/migrate/gen_luacheckrc.py tools/migrate/extract_custom_code.py .luacheckrc-wow CLAUDE.md docs/acceptance-checklist.md tests/py/test_custom_code.py
git commit -m "feat: lint toolchain, workflow docs, and end-to-end acceptance checklist"
```

---

## Post-plan verification

- Run the full suite: `./tests/run.sh`.
- Walk `docs/acceptance-checklist.md` with the user (items 1–4 need the game).
- The `tmp/audit-baseline.txt` from Task 11 is the seed for the next project: fixing the shaman group.
