--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Warlock")
    local _spec  = tostring(_args[2] or "Affliction")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Warlock","Affliction")
sliccNote:RECslot(bis, "28963", "1") sliccNote:RECslot(bis, "29759", "2") sliccNote:RECslot(bis, "24266", "3") sliccNote:RECslot(bis, "28744", "4") sliccNote:RECslot(bis, "28967", "1") sliccNote:RECslot(bis, "29762", "2") sliccNote:RECslot(bis, "21869", "3") sliccNote:RECslot(bis, "28766", "1") sliccNote:RECslot(bis, "30735", "2") sliccNote:RECslot(bis, "28797", "3") sliccNote:RECslot(bis, "28964", "1") sliccNote:RECslot(bis, "29755", "2") sliccNote:RECslot(bis, "21871", "3") sliccNote:RECslot(bis, "28602", "4") sliccNote:RECslot(bis, "24250", "1") sliccNote:RECslot(bis, "28515", "2") sliccNote:RECslot(bis, "28968", "1") sliccNote:RECslot(bis, "29756", "2") sliccNote:RECslot(bis, "30725", "3") sliccNote:RECslot(bis, "28507", "4") sliccNote:RECslot(bis, "28780", "5") sliccNote:RECslot(bis, "24256", "1") sliccNote:RECslot(bis, "28799", "2") sliccNote:RECslot(bis, "24262", "1") sliccNote:RECslot(bis, "28966", "2") sliccNote:RECslot(bis, "29765", "3") sliccNote:RECslot(bis, "30734", "4") sliccNote:RECslot(bis, "21870", "1") sliccNote:RECslot(bis, "28585", "2") sliccNote:RECslot(bis, "28517", "3") sliccNote:RECslot(bis, "28530", "1") sliccNote:RECslot(bis, "28134", "2") sliccNote:RECslot(bis, "28762", "3") sliccNote:RECslot(bis, "30666", "4") sliccNote:RECslot(bis, "28793", "1") sliccNote:RECslot(bis, "32385", "2") sliccNote:RECslot(bis, "29172", "3") sliccNote:RECslot(bis, "28227", "4") sliccNote:RECslot(bis, "28753", "5") sliccNote:RECslot(bis, "29287", "6") sliccNote:RECslot(bis, "27683", "1") sliccNote:RECslot(bis, "29370", "2") sliccNote:RECslot(bis, "22630", "1") sliccNote:RECslot(bis, "30723", "1") sliccNote:RECslot(bis, "28802", "2") sliccNote:RECslot(bis, "28770", "3") sliccNote:RECslot(bis, "28297", "4") sliccNote:RECslot(bis, "31336", "5") sliccNote:RECslot(bis, "23554", "6") sliccNote:RECslot(bis, "29273", "1") sliccNote:RECslot(bis, "28734", "2") sliccNote:RECslot(bis, "28673", "1") sliccNote:RECslot(bis, "29350", "2") sliccNote:RECslot(bis, "28783", "3")