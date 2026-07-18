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

commands["pull-groundtruth"] = function()
  local gt = require("groundtruth")
  os.execute("mkdir -p data/ground-truth")
  gt.import(gt.DUMP_PATH, "data/ground-truth")
  print("ground truth updated in data/ground-truth/")
end

commands["dump-displays"] = function()
  local sv = require("sv")
  local env = sv.load(sv.LIVE_PATH)
  io.write(json.to_json(env.WeakAurasSaved.displays))
end

local cmd = table.remove(arg, 1)
if not cmd or not commands[cmd] then
  io.stderr:write("usage: wa <decode|encode|backup|restore|extract|land|pull-groundtruth|dump-displays> ...\n"); os.exit(2)
end
commands[cmd](arg)
