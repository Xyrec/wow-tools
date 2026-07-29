function()
    return UnitExists("target") and (UnitCreatureType("target") == "Undead" or UnitCreatureType("target") == "Demon") and UnitCanAttack("player", "target")
end