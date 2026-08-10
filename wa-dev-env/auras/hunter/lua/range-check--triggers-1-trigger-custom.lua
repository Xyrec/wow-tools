function()    
    
    if not aura_env.lasta or aura_env.lasta < GetTime() - aura_env.config["throttle"] then
        aura_env.lasta = GetTime()
        
        if UnitExists("target") and UnitIsVisible("target") and UnitCanAttack("player", "target") and (not UnitIsDead("target")) then
            aura_env.one = true
        else 
            aura_env.one = false
        end
    end
    
    return aura_env.one
    
end


