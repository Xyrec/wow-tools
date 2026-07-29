function()
    return UnitExists("target") and UnitCreatureType("target") == "Undead" and UnitCanAttack("player", "target")
end