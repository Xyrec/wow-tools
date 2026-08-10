function(a, e, ...)
    local currentMana = UnitPower("player", 0)
    local fsrDuration = 5

    if e == "COMBAT_LOG_EVENT_UNFILTERED" then
        -- attributable mana gain (Mana Spring, Water Shield, potions...):
        -- remember it so it doesn't count as the global regen tick.
        -- "Drink" is deliberately NOT filtered: drink ticks driving the spark
        -- is intended (drink-walking reads the sip timing off this spark)
        local destGUID = select(8, ...)
        local spellName = select(13, ...)
        local amount = select(15, ...)
        if spellName ~= "Drink" and destGUID == UnitGUID("player") and type(amount) == "number" then
            local now = GetTime()
            if aura_env.energizeTime ~= now then
                aura_env.energizeTime = now
                aura_env.energizeAmount = 0
            end
            aura_env.energizeAmount = aura_env.energizeAmount + amount
        end
        return false
    end

    if currentMana >= UnitPowerMax("player", 0) then
        return false
    end

    if e == "UNIT_POWER_FREQUENT" and currentMana > aura_env.lastMana then
        local gained = currentMana - aura_env.lastMana
        local energized = 0
        if aura_env.energizeTime and GetTime() - aura_env.energizeTime < 0.25 then
            energized = aura_env.energizeAmount or 0
        end
        aura_env.energizeAmount = math.max(0, energized - gained)
        -- only a gain beyond recent energizes is the global 2s regen tick;
        -- ignore ticks inside the FSR (Meditation-style partial regen)
        if gained > energized and GetTime() >= aura_env.lastCast + fsrDuration then
            local duration = 2
            a[""] = {
                show = true,
                changed = true,
                duration = duration,
                expirationTime = GetTime() + duration,
                progressType = "timed",
                autoHide = true
            }
        end
        aura_env.lastMana = currentMana
    elseif e == "UNIT_SPELLCAST_SUCCEEDED" and currentMana < aura_env.lastMana then
        local duration = fsrDuration
        a[""] = {
            show = true,
            changed = true,
            duration = duration,
            expirationTime = GetTime() + duration,
            progressType = "timed",
            autoHide = true
        }
        aura_env.lastMana = currentMana
        aura_env.lastCast = GetTime()
    end
    return true
end