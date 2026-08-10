function()    
    if UnitExists("target") and UnitIsVisible("target") and UnitCanAttack("player", "target") and (not UnitIsDead("target")) then
        return true
    else 
        return false
    end
end