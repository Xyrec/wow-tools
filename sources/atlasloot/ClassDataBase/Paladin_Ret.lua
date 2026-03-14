--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Paladin")
    local _spec  = tostring(_args[2] or "Ret")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Paladin","Ret")
sliccNote:RECslot(bis, "29073", "1") sliccNote:RECslot(bis, "29760", "2") sliccNote:RECslot(bis, "27881", "3") sliccNote:RECslot(bis, "31105", "4") sliccNote:RECslot(bis, "29075", "1") sliccNote:RECslot(bis, "29763", "2") sliccNote:RECslot(bis, "30740", "3") sliccNote:RECslot(bis, "28755", "4") sliccNote:RECslot(bis, "27883", "5") sliccNote:RECslot(bis, "33122", "1") sliccNote:RECslot(bis, "24259", "2") sliccNote:RECslot(bis, "27878", "3") sliccNote:RECslot(bis, "29071", "1") sliccNote:RECslot(bis, "29754", "2") sliccNote:RECslot(bis, "30730", "3") sliccNote:RECslot(bis, "29515", "4") sliccNote:RECslot(bis, "29525", "5") sliccNote:RECslot(bis, "28403", "6") sliccNote:RECslot(bis, "28795", "1") sliccNote:RECslot(bis, "23537", "2") sliccNote:RECslot(bis, "30644", "1") sliccNote:RECslot(bis, "30341", "2") sliccNote:RECslot(bis, "28779", "1") sliccNote:RECslot(bis, "28828", "2") sliccNote:RECslot(bis, "29247", "3") sliccNote:RECslot(bis, "28750", "4") sliccNote:RECslot(bis, "30257", "1") sliccNote:RECslot(bis, "31544", "2") sliccNote:RECslot(bis, "28608", "1") sliccNote:RECslot(bis, "28545", "2") sliccNote:RECslot(bis, "28746", "3") sliccNote:RECslot(bis, "25686", "4") sliccNote:RECslot(bis, "29381", "1") sliccNote:RECslot(bis, "28509", "2") sliccNote:RECslot(bis, "28745", "3") sliccNote:RECslot(bis, "29119", "4") sliccNote:RECslot(bis, "30834", "1") sliccNote:RECslot(bis, "30738", "2") sliccNote:RECslot(bis, "28757", "3") sliccNote:RECslot(bis, "28730", "4") sliccNote:RECslot(bis, "29283", "5") sliccNote:RECslot(bis, "31920", "6") sliccNote:RECslot(bis, "28649", "7") sliccNote:RECslot(bis, "29383", "1") sliccNote:RECslot(bis, "28830", "2") sliccNote:RECslot(bis, "28288", "3") sliccNote:RECslot(bis, "28034", "4") sliccNote:RECslot(bis, "28579", "5") sliccNote:RECslot(bis, "28429", "1") sliccNote:RECslot(bis, "30722", "2") sliccNote:RECslot(bis, "28441", "3") sliccNote:RECslot(bis, "28773", "4") sliccNote:RECslot(bis, "24550", "5") sliccNote:RECslot(bis, "27484", "1")