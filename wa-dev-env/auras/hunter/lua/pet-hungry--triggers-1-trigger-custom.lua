function()
    if UnitExists("pet") and GetPetHappiness() ~= nil and GetPetHappiness() < 3 then
        return true    
    end
end