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

local function dump_book()
  local class = select(2, UnitClass("player"))
  local book = {}
  local i = 1
  while true do
    local name, rank
    if GetSpellBookItemName then
      name, rank = GetSpellBookItemName(i, "spell")
    else
      name, rank = GetSpellName(i, "spell")
    end
    if not name then break end
    local spellId
    if GetSpellBookItemInfo then
      local kind, id = GetSpellBookItemInfo(i, "spell")
      if kind == "SPELL" then spellId = id end
    end
    book[i] = { name = name, rank = rank ~= "" and rank or nil, spellId = spellId }
    i = i + 1
  end
  XyrecDumpDB.spellbook = XyrecDumpDB.spellbook or {}
  XyrecDumpDB.spellbook[class] = book
  print(("XyrecDump: spellbook dumped for %s (%d entries). /reload to persist."):format(class, #book))
end

SLASH_XDUMP1 = "/xdump"
SlashCmdList["XDUMP"] = function(msg)
  local cmd, a, b = msg:match("^(%S*)%s*(%S*)%s*(%S*)")
  if cmd == "spells" then
    dump_spells(tonumber(a) or 1, tonumber(b) or 200000)
  elseif cmd == "talents" then dump_talents()
  elseif cmd == "auras" then dump_auras()
  elseif cmd == "book" then dump_book()
  elseif cmd == "all" then
    dump_talents(); dump_book(); dump_auras()
    dump_spells(tonumber(a) or 1, tonumber(b) or 200000)
  else
    print("XyrecDump usage: /xdump spells [from] [to] | /xdump talents | /xdump book | /xdump auras | /xdump all")
    print("NOTE: data persists to SavedVariables on /reload or logout.")
  end
end
