function()
    local unit = "target"
    
    if not aura_env.lastg or aura_env.lastg < GetTime() - aura_env.config["throttle"] then
        aura_env.lastg = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then
            if CheckInteractDistance(unit, 4) then
                aura_env.seven = true
            else 
                aura_env.seven = false
            end
        end
    end
    
    return aura_env.seven
    
end



