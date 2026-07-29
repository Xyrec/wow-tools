function(event, ...)
    if event == "UNIT_DAMAGE" then
        local current = GetInventoryItemLink("player", GetInventorySlotInfo("MainHandSlot"))
        if current ~= aura_env.mainhand then
            aura_env.stacks = 0
            aura_env.mainhand = current
        end
    elseif event == "PLAYER_ENTERING_WORLD" then
        local isInitialLogin, isReloadingUi = ...
        if isInitialLogin == false and isReloadingUi == false then
            aura_env.stacks = 0
        end
    elseif event == "COMBAT_LOG_EVENT_UNFILTERED" then
        local subevent = select(2, ...)
        local name = select(5, ...)
        local spellID = select(12, ...)
        local stacks = select(16, ...)
        if name ~= UnitName("player") then return end
        if subevent == "SPELL_EXTRA_ATTACKS" then
            aura_env.stacks = aura_env.stacks + 1
            if aura_env.stacks > 4 then aura_env.stacks = 4 end
        elseif subevent == "SWING_DAMAGE" or subevent == "SWING_MISSED" then
            aura_env.stacks = 0
        end
    end
    
    return true
end