function()
    local unit = "target"
    
    if not aura_env.laste or aura_env.laste < GetTime() - aura_env.config["throttle"] then
        aura_env.laste = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then
            if(IsItemInRange("item:9621",unit)) and aura_env.config["sweetspotr"] then
                aura_env.five = true
            else 
                aura_env.five = false
            end
        end
    end
    
    
    
    return aura_env.five
    
end