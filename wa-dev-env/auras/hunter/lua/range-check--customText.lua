function()
    local unit = "target"    
    
    if not aura_env.last or aura_env.last < GetTime() - aura_env.config["throttle"] then
        aura_env.last = GetTime()
        
        if UnitExists(unit) and UnitIsVisible(unit) then
            if IsSpellInRange(GetSpellInfo(2974),unit) == 1 then
                aura_env.rangeDisplay = aura_env.config["melee"]
            elseif IsSpellInRange(GetSpellInfo(75),unit) == 1 then
                if(IsItemInRange("item:9621",unit)) and aura_env.config["sweetspotr"] then
                    aura_env.rangeDisplay = aura_env.config["sweetspot"]
                elseif (IsItemInRange("item:10645",unit)) and aura_env.config["shortranger"] then
                    aura_env.rangeDisplay = aura_env.config["shortrange"]
                    
                elseif CheckInteractDistance(unit, 4) or ((not aura_env.config["longranger"]) and (IsItemInRange("item:18904",unit))) then
                    aura_env.rangeDisplay = aura_env.config["inrange"]
                elseif(IsItemInRange("item:18904",unit)) and aura_env.config["longranger"] then
                    aura_env.rangeDisplay = aura_env.config["longrange"]
                elseif (not IsItemInRange("item:4945",unit)) and aura_env.config["40yardsr"] then 
                    aura_env.rangeDisplay = aura_env.config["40yards"]
                else 
                    aura_env.rangeDisplay = aura_env.config["maxrange"]
                end
            elseif(IsItemInRange("item:10645",unit)) then
                aura_env.rangeDisplay = aura_env.config["deadzone"]
            elseif IsSpellInRange(GetSpellInfo(1130),unit) == 0 and aura_env.config["hmoutofranger"] 
            then
                aura_env.rangeDisplay = aura_env.config["hmoutofrange"] 
            else 
                aura_env.rangeDisplay = aura_env.config["outofrange"]
            end
            
        end
        
        return aura_env.rangeDisplay
        
        
        
    end
    return aura_env.rangeDisplay  
end