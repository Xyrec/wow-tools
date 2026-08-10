function()
    local unit = "target"
    
    if not aura_env.lastl or aura_env.lastl < GetTime() - aura_env.config["throttle"] then
        aura_env.lastl = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then
            if(not IsItemInRange("item:4945",unit)) and aura_env.config["40yardsr"] and (IsSpellInRange(GetSpellInfo(75),unit) == 1) then
                aura_env.twelve = true
            else 
                aura_env.twelve = false
            end
        end
    end
    
    
    return aura_env.twelve
    
end