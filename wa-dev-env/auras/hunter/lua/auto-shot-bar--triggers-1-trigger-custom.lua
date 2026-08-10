function(_, _, cleu, _, _, source_name, _, _, _, target_name, _, _, _, spell_name)
    if source_name == UnitName("player") and cleu == "SPELL_CAST_START" then
        return aura_env.spell_start(spell_name)
    end
    
    if target_name == UnitName("player") and (cleu == "SWING_DAMAGE" or cleu == "SPELL_DAMAGE" or cleu == "ENVIRONMENTAL_DAMAGE") and (aura_env.spell_name == aura_env.spells["aimed"] or aura_env.spell_name == aura_env.spells["steady"]) and aura_env.casting then
        return aura_env.add_push_back()
    end
end