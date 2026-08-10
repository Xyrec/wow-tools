function ()
    if(UnitExists("pettarget")) then 
        local delay = 2
        aura_env.untriggerTime = GetTime() + delay
        return false
    end
    
    if aura_env.untriggerTime and aura_env.untriggerTime > GetTime() then 
        return false
    end
    
    return true
end