function(a, e, t)
    local currEnergy = UnitPower("player", 3)
    local dur = 2
    if (e == "UNIT_POWER_FREQUENT" and currEnergy > (aura_env.lastEnergy or 0))
    or (e == "ENERGYTICK" and t and currEnergy == UnitPowerMax("player", 3))
    then
        if not a[""]  then
            a[""] = {
                show = true,
                changed = true,
                duration = dur,
                expirationTime = GetTime() + dur,
                progressType = "timed"
            }
        else
            local s = a[""]
            s.changed = true
            s.duration = dur
            s.expirationTime = GetTime() + dur
            s.show = true
            C_Timer.After(2, function() WeakAuras.ScanEvents("ENERGYTICK", true) end)
        end
    end
    aura_env.lastEnergy = currEnergy
    return true
end