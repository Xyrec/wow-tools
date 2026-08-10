function()
    local unit = "target"
    
    if not aura_env.lastc or aura_env.lastc < GetTime() - aura_env.config["throttle"] then
        aura_env.lastc = GetTime()
        
        if UnitExists("target") and UnitIsVisible("target") and UnitCanAttack("player", "target") and (not UnitIsDead("target")) then
            if IsSpellInRange(GetSpellInfo(75),unit) == 1 then
                aura_env.three = true
            else 
                aura_env.three = false
                
            end
        end
    end
    
    
    
    return aura_env.three
    
end




