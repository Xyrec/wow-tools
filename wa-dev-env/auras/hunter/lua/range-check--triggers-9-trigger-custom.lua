function()
    local unit = "target"
    
    if not aura_env.lasti or aura_env.lasti < GetTime() - aura_env.config["throttle"] then
        aura_env.lasti = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then
            if(IsItemInRange("item:10645",unit)) and aura_env.config["shortranger"] then
                aura_env.nine = true
            else 
                aura_env.nine = false
            end
        end
    end
    
    
    
    return aura_env.nine
    
end