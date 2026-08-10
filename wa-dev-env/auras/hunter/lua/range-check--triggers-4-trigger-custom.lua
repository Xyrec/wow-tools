function()
    local unit = "target"
    
    if not aura_env.lastd or aura_env.lastd < GetTime() - aura_env.config["throttle"] then
        aura_env.lastd = GetTime()
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then
            if(IsItemInRange("item:10645",unit)) then
                aura_env.four = true
            else 
                aura_env.four = false
            end
        end
    end
    
    return aura_env.four
    
end