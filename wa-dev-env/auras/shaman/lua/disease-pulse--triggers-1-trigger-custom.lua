function(allstates, event)
    local have, name, startTime, duration, icon = GetTotemInfo(3)
    if have and name and name:find("Disease Cleansing Totem", 1, true) then
        local interval = 5
        local elapsed = GetTime() - startTime
        local nextIn = interval - (elapsed % interval)
        allstates[""] = {
            show = true, changed = true,
            progressType = "timed",
            duration = interval,
            expirationTime = GetTime() + nextIn,
            autoHide = false,
            icon = icon, name = name,
        }
        if not aura_env.tickTimer or aura_env.tickTimer:IsCancelled() then
            aura_env.tickTimer = C_Timer.NewTimer(nextIn + 0.05, function()
                aura_env.tickTimer = nil
                WeakAuras.ScanEvents("XYREC_TOTEM_TICK")
            end)
        end
    else
        if aura_env.tickTimer then aura_env.tickTimer:Cancel(); aura_env.tickTimer = nil end
        allstates[""] = { show = false, changed = true }
    end
    return true
end