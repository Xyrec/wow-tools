--== HASTE STUFF ==--

local _dumped_quiver_mapping = {
    [1.15] = {18714,19320,19319,29118,34106,29118,29143,29144,34100,34099},
    [1.14] = {2663,2662},
    [1.13] = {7372,7371},
    [1.12] = {8218,8217},
    [1.11] = {3604,3605},
    [1.10] = {2101,5439,7278,11362,11362,3574,5441,7279,11363,2102,11362},
}
aura_env.quivers = {}
for haste, quivers in pairs(_dumped_quiver_mapping) do
    for _, quiver in ipairs(quivers) do
        aura_env.quivers[quiver] = haste
    end
end

aura_env.haste = function()
    local haste = 1 + GetRangedHaste() / 100
    for i=1,4 do
        local bag_name = C_Container.GetBagName(i)
        
        if bag_name ~= nil then
            local bag_id = GetItemInfoInstant(bag_name)
            if aura_env.quivers[bag_id] ~= nil then
                return haste * aura_env.quivers[bag_id]
            end
        end
    end
    
    return haste
end

--== SPELL INFO ==--

aura_env.spells = {
    aimed = GetSpellInfo(19434),
    multi = GetSpellInfo(2643),
    auto = GetSpellInfo(75),
}
aura_env.spell_names = {}
for _, name in pairs(aura_env.spells) do
    tinsert(aura_env.spell_names, name)
end

--== on spell cast ==--

aura_env.casting = false
aura_env.spell_name = "none"
aura_env.spell_start = function(spell_name)
    if tContains(aura_env.spell_names, spell_name) then
        if spell_name == aura_env.spells.auto and aura_env.config.show_auto_cast == false then
            return false
        end
        
        aura_env.pushback_total = 0
        aura_env.push = 0
        aura_env.push_number = 0
        
        local _, _, spell_icon, cast_time, _, _, spell_id = GetSpellInfo(spell_name)
        
        aura_env.spell_name = spell_name
        aura_env.spell_icon = spell_icon
        aura_env.cast_time = max(cast_time, 500) -- MS, not S
        aura_env.casting = true
        
        if aura_env.spell_name == aura_env.spells["aimed"] then
            aura_env.cast_time = 3500 -- i fucking hate classic
        end
        
        aura_env.duration = aura_env.cast_time / 1000 / aura_env.haste()
        aura_env.expiration_time = aura_env.duration + GetTime()
        
        return true
    end
end

--== on damage taken ==--

aura_env.expiration_time = GetTime()
aura_env.pushback = false
aura_env.push_backs = {1, 0.8, 0.6, 0.4, 0.2}
aura_env.push_number = 0
aura_env.add_push_back = function()
    aura_env.push_number = min(aura_env.push_number + 1, 5)
    
    if (aura_env.duration - (aura_env.expiration_time - GetTime())) < aura_env.push_backs[aura_env.push_number] then
        aura_env.pushback_total = aura_env.pushback_total + (aura_env.duration - (aura_env.expiration_time - GetTime()))
        aura_env.push = aura_env.duration - (aura_env.expiration_time - GetTime())
    else
        aura_env.push = aura_env.push_backs[aura_env.push_number]
        aura_env.pushback_total = aura_env.pushback_total + aura_env.push_backs[aura_env.push_number]
    end
    aura_env.pushback = true
    
    aura_env.expiration_time = aura_env.expiration_time + aura_env.push
    return aura_env.casting
end



