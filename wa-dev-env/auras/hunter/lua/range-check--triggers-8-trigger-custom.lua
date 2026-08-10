function()
    local unit = "target"
    
    if not aura_env.lasth or aura_env.lasth < GetTime() - aura_env.config["throttle"] then
        aura_env.lasth = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then
            if (not (IsSpellInRange(GetSpellInfo(1130),unit) == 1)) and aura_env.config["hmoutofranger"] then
                aura_env.eight = true
            else 
                aura_env.eight = false
            end
        end
    end
    
    
    
    return aura_env.eight
    
end