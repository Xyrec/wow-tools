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
