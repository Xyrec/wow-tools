function()
    if aura_env.region then
        local mana = UnitPower("player", Enum.PowerType.Mana)
        aura_env.region.text3:SetText(mana)
    end
end











