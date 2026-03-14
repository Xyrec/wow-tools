--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Warrior")
    local _spec  = tostring(_args[2] or "Arms")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Warrior","Arms")
sliccNote:RECslot(bis, "29021", "1") sliccNote:RECslot(bis, "29761", "2") sliccNote:RECslot(bis, "32087", "3") sliccNote:RECslot(bis, "29023", "1") sliccNote:RECslot(bis, "29764", "2") sliccNote:RECslot(bis, "30740", "3") sliccNote:RECslot(bis, "33173", "4") sliccNote:RECslot(bis, "24259", "1") sliccNote:RECslot(bis, "30729", "2") sliccNote:RECslot(bis, "28672", "3") sliccNote:RECslot(bis, "29019", "1") sliccNote:RECslot(bis, "29753", "2") sliccNote:RECslot(bis, "30730", "3") sliccNote:RECslot(bis, "23522", "4") sliccNote:RECslot(bis, "24544", "5") sliccNote:RECslot(bis, "31548", "6") sliccNote:RECslot(bis, "28795", "1") sliccNote:RECslot(bis, "23537", "2") sliccNote:RECslot(bis, "28381", "3") sliccNote:RECslot(bis, "30399", "4") sliccNote:RECslot(bis, "28824", "1") sliccNote:RECslot(bis, "30644", "2") sliccNote:RECslot(bis, "29020", "3") sliccNote:RECslot(bis, "29758", "4") sliccNote:RECslot(bis, "25685", "5") sliccNote:RECslot(bis, "27497", "6") sliccNote:RECslot(bis, "28779", "1") sliccNote:RECslot(bis, "28828", "2") sliccNote:RECslot(bis, "27985", "3") sliccNote:RECslot(bis, "30739", "1") sliccNote:RECslot(bis, "28741", "2") sliccNote:RECslot(bis, "29022", "3") sliccNote:RECslot(bis, "29767", "4") sliccNote:RECslot(bis, "30538", "5") sliccNote:RECslot(bis, "28608", "1") sliccNote:RECslot(bis, "25686", "2") sliccNote:RECslot(bis, "28545", "3") sliccNote:RECslot(bis, "30401", "4") sliccNote:RECslot(bis, "29381", "1") sliccNote:RECslot(bis, "29349", "2") sliccNote:RECslot(bis, "28509", "3") sliccNote:RECslot(bis, "30738", "1") sliccNote:RECslot(bis, "28757", "2") sliccNote:RECslot(bis, "28730", "3") sliccNote:RECslot(bis, "30834", "4") sliccNote:RECslot(bis, "28649", "5") sliccNote:RECslot(bis, "29283", "6") sliccNote:RECslot(bis, "29379", "7") sliccNote:RECslot(bis, "28830", "1") sliccNote:RECslot(bis, "29383", "2") sliccNote:RECslot(bis, "21670", "3") sliccNote:RECslot(bis, "28438", "1") sliccNote:RECslot(bis, "28657", "2") sliccNote:RECslot(bis, "28767", "3") sliccNote:RECslot(bis, "23054", "4") sliccNote:RECslot(bis, "28729", "1") sliccNote:RECslot(bis, "30733", "2") sliccNote:RECslot(bis, "28429", "1") sliccNote:RECslot(bis, "28573", "2") sliccNote:RECslot(bis, "28773", "3") sliccNote:RECslot(bis, "30724", "1") sliccNote:RECslot(bis, "28772", "2") sliccNote:RECslot(bis, "30279", "3") sliccNote:RECslot(bis, "29211", "4") sliccNote:RECslot(bis, "22811", "5")