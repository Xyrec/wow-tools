--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
local bis = (function(...)
    local _args = {...}
    local _class = tostring(_args[1] or "Priest")
    local _spec  = tostring(_args[2] or "Shadow")
    local _fn = sliccNote.RegisterBIS
    assert(type(_fn) == "function", "Data missing")
    -- invoke (_class,_spec))
    local _res = _fn(sliccNote, _class, _spec)
    return _res
end)("Priest","Shadow")
sliccNote:RECslot(bis, "24266", "1") sliccNote:RECslot(bis, "28804", "2") sliccNote:RECslot(bis, "29058", "3") sliccNote:RECslot(bis, "29761", "4") sliccNote:RECslot(bis, "21869", "1") sliccNote:RECslot(bis, "27778", "2") sliccNote:RECslot(bis, "29060", "3") sliccNote:RECslot(bis, "29764", "4") sliccNote:RECslot(bis, "28570", "1") sliccNote:RECslot(bis, "28766", "2") sliccNote:RECslot(bis, "28797", "3") sliccNote:RECslot(bis, "21871", "1") sliccNote:RECslot(bis, "29056", "2") sliccNote:RECslot(bis, "29753", "3") sliccNote:RECslot(bis, "28515", "1") sliccNote:RECslot(bis, "28477", "2") sliccNote:RECslot(bis, "28507", "1") sliccNote:RECslot(bis, "28780", "2") sliccNote:RECslot(bis, "30725", "3") sliccNote:RECslot(bis, "28799", "1") sliccNote:RECslot(bis, "24262", "1") sliccNote:RECslot(bis, "30734", "2") sliccNote:RECslot(bis, "28594", "3") sliccNote:RECslot(bis, "21870", "1") sliccNote:RECslot(bis, "28517", "2") sliccNote:RECslot(bis, "28585", "3") sliccNote:RECslot(bis, "28179", "4") sliccNote:RECslot(bis, "30666", "1") sliccNote:RECslot(bis, "24121", "2") sliccNote:RECslot(bis, "24116", "3") sliccNote:RECslot(bis, "33921", "4") sliccNote:RECslot(bis, "18814", "5") sliccNote:RECslot(bis, "31693", "6") sliccNote:RECslot(bis, "21709", "1") sliccNote:RECslot(bis, "23031", "2") sliccNote:RECslot(bis, "28753", "3") sliccNote:RECslot(bis, "29352", "4") sliccNote:RECslot(bis, "28793", "5") sliccNote:RECslot(bis, "32385", "6") sliccNote:RECslot(bis, "28555", "7") sliccNote:RECslot(bis, "29287", "8") sliccNote:RECslot(bis, "34073", "9") sliccNote:RECslot(bis, "29370", "1") sliccNote:RECslot(bis, "27683", "2") sliccNote:RECslot(bis, "28789", "3") sliccNote:RECslot(bis, "38290", "4") sliccNote:RECslot(bis, "28770", "1") sliccNote:RECslot(bis, "30723", "2") sliccNote:RECslot(bis, "33687", "3") sliccNote:RECslot(bis, "30832", "4") sliccNote:RECslot(bis, "23554", "5") sliccNote:RECslot(bis, "29272", "1") sliccNote:RECslot(bis, "32872", "1") sliccNote:RECslot(bis, "28673", "2")