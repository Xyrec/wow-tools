--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Druid")
    local _spec  = tostring(_args[2] or "Feral")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Druid","Feral")
sliccNote:RECslot(bis, "8345", "1") sliccNote:RECslot(bis, "29100", "1") sliccNote:RECslot(bis, "29764", "2") sliccNote:RECslot(bis, "27797", "3") sliccNote:RECslot(bis, "28755", "4") sliccNote:RECslot(bis, "28672", "1") sliccNote:RECslot(bis, "24259", "2") sliccNote:RECslot(bis, "31255", "3") sliccNote:RECslot(bis, "29096", "1") sliccNote:RECslot(bis, "29753", "2") sliccNote:RECslot(bis, "30730", "3") sliccNote:RECslot(bis, "28601", "4") sliccNote:RECslot(bis, "29525", "5") sliccNote:RECslot(bis, "29246", "1") sliccNote:RECslot(bis, "28171", "2") sliccNote:RECslot(bis, "21602", "3") sliccNote:RECslot(bis, "28506", "1") sliccNote:RECslot(bis, "30644", "2") sliccNote:RECslot(bis, "29507", "3") sliccNote:RECslot(bis, "27509", "4") sliccNote:RECslot(bis, "29247", "1") sliccNote:RECslot(bis, "28750", "2") sliccNote:RECslot(bis, "28828", "3") sliccNote:RECslot(bis, "28741", "1") sliccNote:RECslot(bis, "31544", "2") sliccNote:RECslot(bis, "28545", "1") sliccNote:RECslot(bis, "25686", "2") sliccNote:RECslot(bis, "24114", "1") sliccNote:RECslot(bis, "29381", "2") sliccNote:RECslot(bis, "29119", "3") sliccNote:RECslot(bis, "28509", "4") sliccNote:RECslot(bis, "28745", "5") sliccNote:RECslot(bis, "30834", "1") sliccNote:RECslot(bis, "28649", "2") sliccNote:RECslot(bis, "28791", "3") sliccNote:RECslot(bis, "32385", "4") sliccNote:RECslot(bis, "28757", "5") sliccNote:RECslot(bis, "30738", "6") sliccNote:RECslot(bis, "30365", "7") sliccNote:RECslot(bis, "29283", "8") sliccNote:RECslot(bis, "28830", "1") sliccNote:RECslot(bis, "29383", "2") sliccNote:RECslot(bis, "28034", "3") sliccNote:RECslot(bis, "28658", "1") sliccNote:RECslot(bis, "28476", "2") sliccNote:RECslot(bis, "29390", "1") sliccNote:RECslot(bis, "28372", "2") 