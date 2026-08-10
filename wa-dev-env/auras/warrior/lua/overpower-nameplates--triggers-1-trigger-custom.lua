function(allstates, event, unit, subEvent, spellID, sourceGUID, _, _, _, destGUID, _, destFlags, _, ...)
    local changed = false
    
    if event=="COMBAT_LOG_EVENT_UNFILTERED" then
        local missType = subEvent=="SWING_MISSED" and ... or select(4,...)
        
        if missType == "DODGE" and sourceGUID == UnitGUID("player") then
            allstates[destGUID] = {
                changed = true,
                show = true,          
                autoHide = true,
                progressType = "timed",
                expirationTime = GetTime() + aura_env.config.duration,
                duration = aura_env.config.duration,
                unit = aura_env.units[destGUID]
            }
            changed = true
        end
    elseif event=="UNIT_SPELLCAST_SUCCEEDED" and aura_env.overpower[spellID] then
        -- Clear all procs when we cast Overpower, since we can't cast it again before they expire
        for _, state in pairs(allstates) do
            state.show = false;
            state.changed = true;
        end
        changed = true
    elseif event=="PLAYER_TARGET_CHANGED" then
        -- Clear all procs when we change targets
        for _, state in pairs(allstates) do
            state.show = false;
            state.changed = true;
        end
        changed = true
    elseif event=="NAME_PLATE_UNIT_ADDED" then
        if unit then
            aura_env.units[UnitGUID(unit)] = unit
        end
    elseif event=="NAME_PLATE_UNIT_REMOVED" then
        if unit then
            local guid = UnitGUID(unit)
            aura_env.units[guid] = nil
            
            if allstates[guid] then
                allstates[guid] = {
                    changed = true,
                    show = false
                }
                changed = true
            end
        end
    end
    
    return changed
end