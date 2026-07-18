-- Standalone loader for the vendored WeakAuras libraries.
-- Vendored files are UNMODIFIED; any adaptation lives here.
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
