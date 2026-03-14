--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Rogue")
    local _spec  = tostring(_args[2] or "Combat")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Rogue","Combat")
sliccNote:RECslot(bis, "29044", "1") sliccNote:RECslot(bis, "29760", "2") sliccNote:RECslot(bis, "28732", "3") sliccNote:RECslot(bis, "28796", "4") sliccNote:RECslot(bis, "27797", "1") sliccNote:RECslot(bis, "29047", "2") sliccNote:RECslot(bis, "29763", "3") sliccNote:RECslot(bis, "28755", "4") sliccNote:RECslot(bis, "28672", "1") sliccNote:RECslot(bis, "24259", "2") sliccNote:RECslot(bis, "28777", "3") sliccNote:RECslot(bis, "29045", "1") sliccNote:RECslot(bis, "29754", "2") sliccNote:RECslot(bis, "30730", "3") sliccNote:RECslot(bis, "28264", "4") sliccNote:RECslot(bis, "29246", "1") sliccNote:RECslot(bis, "27531", "1") sliccNote:RECslot(bis, "30644", "2") sliccNote:RECslot(bis, "29048", "3") sliccNote:RECslot(bis, "29757", "4") sliccNote:RECslot(bis, "28506", "5") sliccNote:RECslot(bis, "29247", "1") sliccNote:RECslot(bis, "28828", "2") sliccNote:RECslot(bis, "28750", "3") sliccNote:RECslot(bis, "28741", "1") sliccNote:RECslot(bis, "29046", "2") sliccNote:RECslot(bis, "29766", "3") sliccNote:RECslot(bis, "27837", "4") sliccNote:RECslot(bis, "28545", "1") sliccNote:RECslot(bis, "25686", "2") sliccNote:RECslot(bis, "29381", "1") sliccNote:RECslot(bis, "24114", "2") sliccNote:RECslot(bis, "28509", "3") sliccNote:RECslot(bis, "28757", "1") sliccNote:RECslot(bis, "28649", "2") sliccNote:RECslot(bis, "30738", "3") sliccNote:RECslot(bis, "31920", "4") sliccNote:RECslot(bis, "29283", "5") sliccNote:RECslot(bis, "28791", "6") sliccNote:RECslot(bis, "32385", "7") sliccNote:RECslot(bis, "28830", "1") sliccNote:RECslot(bis, "29383", "2") sliccNote:RECslot(bis, "28288", "3") sliccNote:RECslot(bis, "28579", "4") sliccNote:RECslot(bis, "28438", "1") sliccNote:RECslot(bis, "28295", "2") sliccNote:RECslot(bis, "31332", "3") sliccNote:RECslot(bis, "28729", "4") sliccNote:RECslot(bis, "30733", "5") sliccNote:RECslot(bis, "28768", "6 Offhand") sliccNote:RECslot(bis, "28312", "7 Offhand") sliccNote:RECslot(bis, "28307", "1") sliccNote:RECslot(bis, "28189", "2") sliccNote:RECslot(bis, "29275", "3 Offhand") sliccNote:RECslot(bis, "29151", "1") sliccNote:RECslot(bis, "29152", "2") sliccNote:RECslot(bis, "30724", "3") sliccNote:RECslot(bis, "28772", "4")