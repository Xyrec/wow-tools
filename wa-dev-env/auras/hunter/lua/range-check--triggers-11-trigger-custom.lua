
function()
    local unit = "target"
    
    if not aura_env.lastk or aura_env.lastk < GetTime() - aura_env.config["throttle"] then
        aura_env.lastk = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) and UnitCanAttack("player", unit) and (not UnitIsDead(unit)) then 
            
            if  aura_env.config["longranger"] then
                aura_env.eleven = true
            else 
                aura_env.eleven = false
            end
        end
    end 
    
    
    return aura_env.eleven
    
end




