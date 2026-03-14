--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Shaman")
    local _spec  = tostring(_args[2] or "Ele")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Shaman","Ele")
sliccNote:RECslot(bis, "29035", "1") sliccNote:RECslot(bis, "29760", "2") sliccNote:RECslot(bis, "28583", "3") sliccNote:RECslot(bis, "29037", "1") sliccNote:RECslot(bis, "29763", "2") sliccNote:RECslot(bis, "32078", "3") sliccNote:RECslot(bis, "28797", "1") sliccNote:RECslot(bis, "28766", "2") sliccNote:RECslot(bis, "30735", "3") sliccNote:RECslot(bis, "29519", "1") sliccNote:RECslot(bis, "29522", "2") sliccNote:RECslot(bis, "29033", "3") sliccNote:RECslot(bis, "29754", "4") sliccNote:RECslot(bis, "29521", "1") sliccNote:RECslot(bis, "29523", "2") sliccNote:RECslot(bis, "28638", "3") sliccNote:RECslot(bis, "28780", "1") sliccNote:RECslot(bis, "28507", "2") sliccNote:RECslot(bis, "29034", "3") sliccNote:RECslot(bis, "29757", "4") sliccNote:RECslot(bis, "29520", "1") sliccNote:RECslot(bis, "24256", "2") sliccNote:RECslot(bis, "29524", "3") sliccNote:RECslot(bis, "28799", "4") sliccNote:RECslot(bis, "24262", "1") sliccNote:RECslot(bis, "30734", "2") sliccNote:RECslot(bis, "28517", "1") sliccNote:RECslot(bis, "28810", "2") sliccNote:RECslot(bis, "28406", "3") sliccNote:RECslot(bis, "28762", "1") sliccNote:RECslot(bis, "28530", "2") sliccNote:RECslot(bis, "28134", "3") sliccNote:RECslot(bis, "30667", "1") sliccNote:RECslot(bis, "28753", "2") sliccNote:RECslot(bis, "29287", "3") sliccNote:RECslot(bis, "29126", "4") sliccNote:RECslot(bis, "31290", "5") sliccNote:RECslot(bis, "28785", "1") sliccNote:RECslot(bis, "29370", "2") sliccNote:RECslot(bis, "27683", "3") sliccNote:RECslot(bis, "30723", "1") sliccNote:RECslot(bis, "28770", "2") sliccNote:RECslot(bis, "32450", "3") sliccNote:RECslot(bis, "29273", "1") sliccNote:RECslot(bis, "29268", "2") sliccNote:RECslot(bis, "28734", "3") sliccNote:RECslot(bis, "28603", "4") sliccNote:RECslot(bis, "28248", "1")