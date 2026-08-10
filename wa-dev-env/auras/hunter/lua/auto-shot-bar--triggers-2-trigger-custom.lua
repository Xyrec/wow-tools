function(_, _, _, spell_id)
    if spell_id == 75 and aura_env.config.show_auto_reload then -- auto
        return true
    end
end