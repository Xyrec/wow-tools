function()
    local unit = "target"
    
    if not aura_env.lastf or aura_env.lastf < GetTime() - aura_env.config["throttle"] then
        aura_env.lastf = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then
            if(IsItemInRange("item:18904",unit)) then
                aura_env.six = true
            else 
                aura_env.six = false
            end
        end
    end
    return aura_env.six
    
end