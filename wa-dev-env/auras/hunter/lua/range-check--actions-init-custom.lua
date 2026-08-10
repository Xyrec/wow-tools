function(allstates)
    if aura_env.states[1].expirationTime then
        local remaining = aura_env.states[1].expirationTime - GetTime()
        return remaining < aura_env.config.throttle
    end
end


