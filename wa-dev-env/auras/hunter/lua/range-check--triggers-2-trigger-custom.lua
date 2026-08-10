function()
    local unit = "target"
    
    if not aura_env.lastb or aura_env.lastb < GetTime() - aura_env.config["throttle"] then
        aura_env.lastb = GetTime()
        
        if UnitExists("target") and UnitIsVisible("target") and UnitCanAttack("player", "target") and (not UnitIsDead("target")) then
            if IsSpellInRange(GetSpellInfo(2974),unit) == 1 then
                aura_env.two = true
            else 
                aura_env.two = false
            end
        end
    end
    
    
    return aura_env.two
    
end