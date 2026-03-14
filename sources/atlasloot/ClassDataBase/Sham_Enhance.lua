--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Shaman")
    local _spec  = tostring(_args[2] or "Enhance")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Shaman","Enhance")
sliccNote:RECslot(bis, "29040", "1") sliccNote:RECslot(bis, "29760", "2") sliccNote:RECslot(bis, "28732", "3") sliccNote:RECslot(bis, "28224", "4") sliccNote:RECslot(bis, "29043", "1") sliccNote:RECslot(bis, "29763", "2") sliccNote:RECslot(bis, "28755", "3") sliccNote:RECslot(bis, "27797", "4") sliccNote:RECslot(bis, "24259", "1") sliccNote:RECslot(bis, "28672", "2") sliccNote:RECslot(bis, "29038", "1") sliccNote:RECslot(bis, "29754", "2") sliccNote:RECslot(bis, "30730", "3") sliccNote:RECslot(bis, "29525", "4") sliccNote:RECslot(bis, "29515", "5") sliccNote:RECslot(bis, "25997", "6") sliccNote:RECslot(bis, "28514", "1") sliccNote:RECslot(bis, "29527", "2") sliccNote:RECslot(bis, "29517", "3") sliccNote:RECslot(bis, "30644", "1") sliccNote:RECslot(bis, "28828", "1") sliccNote:RECslot(bis, "29526", "2") sliccNote:RECslot(bis, "29516", "3") sliccNote:RECslot(bis, "29247", "4") sliccNote:RECslot(bis, "28741", "1") sliccNote:RECslot(bis, "31544", "2") sliccNote:RECslot(bis, "28545", "1") sliccNote:RECslot(bis, "28746", "2") sliccNote:RECslot(bis, "25686", "3") sliccNote:RECslot(bis, "29381", "1") sliccNote:RECslot(bis, "28509", "2") sliccNote:RECslot(bis, "28757", "1") sliccNote:RECslot(bis, "28649", "2") sliccNote:RECslot(bis, "30834", "3") sliccNote:RECslot(bis, "30738", "4") sliccNote:RECslot(bis, "29283", "5") sliccNote:RECslot(bis, "28830", "1") sliccNote:RECslot(bis, "29383", "2") sliccNote:RECslot(bis, "28313", "1 Mainhand") sliccNote:RECslot(bis, "28308", "2 ") sliccNote:RECslot(bis, "28767", "3 Mainhand") sliccNote:RECslot(bis, "27872", "4 Offhand") sliccNote:RECslot(bis, "28944", "5 Offhand") sliccNote:RECslot(bis, "28920", "6 Offhand") sliccNote:RECslot(bis, "28657", "7") sliccNote:RECslot(bis, "28438", "8 Mainhand") sliccNote:RECslot(bis, "28432", "9 Mainhand") sliccNote:RECslot(bis, "27815", "1")