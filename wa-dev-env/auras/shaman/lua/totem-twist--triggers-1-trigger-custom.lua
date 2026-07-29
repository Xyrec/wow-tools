function(a, e, ...)
    if e == "COMBAT_LOG_EVENT_UNFILTERED" then
        local subevent = select(2, ...)
        local sourceGUID = select(4, ...)
        local spellName = select(13, ...)
        if subevent == "SPELL_CAST_SUCCESS"
                and sourceGUID == UnitGUID("player")
                and spellName == "Windfury Totem" then
            -- arm + start the 10s twist window (WF party buff lingers ~10s
            -- after the totem is swapped away)
            a[""] = {
                show = true,
                changed = true,
                progressType = "timed",
                duration = 10,
                expirationTime = GetTime() + 10,
                autoHide = false
            }
            return true
        end
        return false
    end
    -- PLAYER_REGEN_ENABLED / PLAYER_ENTERING_WORLD: leaving combat disarms
    if a[""] then
        a[""] = nil
        return true
    end
    return false
end