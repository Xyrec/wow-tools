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
