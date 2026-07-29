function(a, e, t)
    local currentMana = UnitPower("player" , 0)
    local fsrDuration = 5
    
    if currentMana >= UnitPowerMax("player", 0) then
        return false
    end
    
    if e == "UNIT_POWER_FREQUENT" and currentMana > aura_env.lastMana then
        
        -- if the condition isn't met, the current tick occured during FSR duration
        -- probably due to talents like Meditation or set bonuses
        -- we will therefore ignore this tick and not overwrite the animation
        if GetTime() >= aura_env.lastCast + fsrDuration then 
            
            local duration = 2
            a[""] = {
                show = true,
                changed = true,
                duration = duration,
                expirationTime = GetTime() + duration,
                progressType = "timed",
                autoHide = true
            }
        end
        
        -- print mana gained from tick for debugging:
        -- print('mana tick: ' .. (currentMana - aura_env.lastMana))
        
        aura_env.lastMana = currentMana
        
    elseif e == "UNIT_SPELLCAST_SUCCEEDED" and currentMana < aura_env.lastMana then
        local duration = fsrDuration
        a[""] = {
            show = true,
            changed = true,
            duration = duration,
            expirationTime = GetTime() + duration,
            progressType = "timed",
            autoHide = true
        }
        aura_env.lastMana = currentMana
        aura_env.lastCast = GetTime()
    end
    
    --aura_env.lastMana = currentMana
    return true
end