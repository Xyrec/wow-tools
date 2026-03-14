--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Priest")
    local _spec  = tostring(_args[2] or "Holy")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Priest","Holy")
sliccNote:RECslot(bis, "29049", "1") sliccNote:RECslot(bis, "29761", "2") sliccNote:RECslot(bis, "28756", "3") sliccNote:RECslot(bis, "21874", "1") sliccNote:RECslot(bis, "29054", "2") sliccNote:RECslot(bis, "29764", "3") sliccNote:RECslot(bis, "28612", "4") sliccNote:RECslot(bis, "28765", "1") sliccNote:RECslot(bis, "29354", "2") sliccNote:RECslot(bis, "31329", "3") sliccNote:RECslot(bis, "28582", "4") sliccNote:RECslot(bis, "21875", "1") sliccNote:RECslot(bis, "29050", "2") sliccNote:RECslot(bis, "29753", "3") sliccNote:RECslot(bis, "28578", "4") sliccNote:RECslot(bis, "29183", "1") sliccNote:RECslot(bis, "28511", "2") sliccNote:RECslot(bis, "29249", "3") sliccNote:RECslot(bis, "28508", "1") sliccNote:RECslot(bis, "29055", "2") sliccNote:RECslot(bis, "29758", "3") sliccNote:RECslot(bis, "24393", "4") sliccNote:RECslot(bis, "27536", "5") sliccNote:RECslot(bis, "21873", "1") sliccNote:RECslot(bis, "28652", "2") sliccNote:RECslot(bis, "30727", "1") sliccNote:RECslot(bis, "28742", "2") sliccNote:RECslot(bis, "30543", "3") sliccNote:RECslot(bis, "29053", "4") sliccNote:RECslot(bis, "29767", "5") sliccNote:RECslot(bis, "28663", "1") sliccNote:RECslot(bis, "29251", "2") sliccNote:RECslot(bis, "30726", "1") sliccNote:RECslot(bis, "28822", "2") sliccNote:RECslot(bis, "28609", "3") sliccNote:RECslot(bis, "28731", "4") sliccNote:RECslot(bis, "30736", "1") sliccNote:RECslot(bis, "29290", "2") sliccNote:RECslot(bis, "28763", "3") sliccNote:RECslot(bis, "28661", "4") sliccNote:RECslot(bis, "28790", "5") sliccNote:RECslot(bis, "32385", "6") sliccNote:RECslot(bis, "29376", "1") sliccNote:RECslot(bis, "28823", "2") sliccNote:RECslot(bis, "19288", "3") sliccNote:RECslot(bis, "28771", "1") sliccNote:RECslot(bis, "30732", "2") sliccNote:RECslot(bis, "32451", "3") sliccNote:RECslot(bis, "28522", "4") sliccNote:RECslot(bis, "28782", "5") sliccNote:RECslot(bis, "28604", "6") sliccNote:RECslot(bis, "29170", "1") sliccNote:RECslot(bis, "29274", "2") sliccNote:RECslot(bis, "28728", "3") sliccNote:RECslot(bis, "28525", "4") sliccNote:RECslot(bis, "28588", "1") sliccNote:RECslot(bis, "27885", "2") sliccNote:RECslot(bis, "23009", "3")