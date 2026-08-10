function()
    local unit = "target"
    
    if not aura_env.lastj or aura_env.lastj < GetTime() - aura_env.config["throttle"] then
        aura_env.lastj = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then 
            
            if (aura_env.config["longranger"] and CheckInteractDistance(unit, 4)) or ((not aura_env.config["longranger"]) and (IsItemInRange("item:18904",unit))) then
                
                
                aura_env.ten = true
            else 
                aura_env.ten = false
            end
        end
    end
    
    
    
    return aura_env.ten
    
end


