--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Shaman")
    local _spec  = tostring(_args[2] or "Resto")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Shaman","Resto")
sliccNote:RECslot(bis, "29028", "1") sliccNote:RECslot(bis, "29760", "2") sliccNote:RECslot(bis, "30728", "3") sliccNote:RECslot(bis, "24264", "4") sliccNote:RECslot(bis, "29031", "1") sliccNote:RECslot(bis, "29763", "2") sliccNote:RECslot(bis, "21874", "3") sliccNote:RECslot(bis, "28631", "4") sliccNote:RECslot(bis, "28765", "1") sliccNote:RECslot(bis, "31329", "2") sliccNote:RECslot(bis, "29522", "1") sliccNote:RECslot(bis, "21875", "2") sliccNote:RECslot(bis, "29029", "3") sliccNote:RECslot(bis, "29754", "4") sliccNote:RECslot(bis, "29523", "1") sliccNote:RECslot(bis, "28503", "2") sliccNote:RECslot(bis, "28520", "1") sliccNote:RECslot(bis, "28521", "2") sliccNote:RECslot(bis, "29032", "3") sliccNote:RECslot(bis, "29757", "4") sliccNote:RECslot(bis, "29524", "1") sliccNote:RECslot(bis, "21873", "2") sliccNote:RECslot(bis, "28567", "3") sliccNote:RECslot(bis, "28751", "1") sliccNote:RECslot(bis, "28591", "2") sliccNote:RECslot(bis, "24261", "3") sliccNote:RECslot(bis, "30737", "1") sliccNote:RECslot(bis, "28752", "2") sliccNote:RECslot(bis, "28609", "1") sliccNote:RECslot(bis, "30726", "2") sliccNote:RECslot(bis, "28822", "3") sliccNote:RECslot(bis, "31691", "4") sliccNote:RECslot(bis, "28763", "1") sliccNote:RECslot(bis, "28790", "2") sliccNote:RECslot(bis, "32385", "3") sliccNote:RECslot(bis, "29169", "4") sliccNote:RECslot(bis, "29168", "5") sliccNote:RECslot(bis, "28259", "6") sliccNote:RECslot(bis, "29814", "7") sliccNote:RECslot(bis, "31923", "8") sliccNote:RECslot(bis, "29376", "1") sliccNote:RECslot(bis, "28190", "2") sliccNote:RECslot(bis, "28771", "1") sliccNote:RECslot(bis, "32451", "2") sliccNote:RECslot(bis, "28522", "3") sliccNote:RECslot(bis, "29458", "1") sliccNote:RECslot(bis, "28728", "2") sliccNote:RECslot(bis, "28754", "3") sliccNote:RECslot(bis, "28523", "1") sliccNote:RECslot(bis, "27544", "2")