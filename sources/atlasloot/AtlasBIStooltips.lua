--     _   _   _                 _                 _   _____  ____    ____ 
--    / \ | |_| |  __ _   ___  | |  ___    ___   | |_|_   _|| __ )  / ___|
--   / _ \| __| | / _` | / __| | | / _ \  / _ \  | __| | |  |  _ \ | |    
--  / ___ \ |_| || (_| | \__ \ | || (_) || (_) | | |_  | |  | |_) || |___ 
-- /_/   \_\__|_| \__,_| |___/ |_| \___/  \___/   \__| |_|  |____/  \____|
--
--[[
    ***********************************************************************
    * PROJECT: AtlasBiS Integration Module                                *
    * MODULE: Core Renderer & Data Handler                                *
    * VERSION: 1.0.1                           				              *
    * DESC: Handles tooltip injection via native API hooking mechanisms.  *
    ***********************************************************************
]]

local _G = _G
local pairs, ipairs, select, tostring, type = pairs, ipairs, select, tostring, type
local string_format, string_match = string.format, string.match
local math_floor = math.floor


-- SYSTEM CONSTANTS & ASSETS

local ADDON_NAME, PrivateNamespace = ...
local ASSET_ROOT_PATH = [[Interface\AddOns\AtlasBIStooltips\media\]]

-- Global namespace definition for Atlas integration
sliccNote.BIS = sliccNote.BIS or {}
sliccNote.Items = sliccNote.Items or {}

-- Internal configuration for visual rendering
local RENDER_CONFIG = {
    ICON_SIZE = 64,
    ICON_PADDING = 6,
    DISPLAY_SIZE = 14,
    TEXTURE_DIM = 256,
    HEADER_COLOR = { r = 1.0, g = 0.82, b = 0.0 }
}


-- UTILITY: LOGGING WRAPPER

local Logger = {
    _prefix = "|cFF00FF00[System]|r ",
    Log = function(self, message)
        -- Placeholder for future debugging output streams
        -- print(self._prefix .. tostring(message)) 
        return nil
    end
}


-- SUBSYSTEM: CONFIGURATION MANAGER

local ConfigManager = {}

function ConfigManager:Initialize()
    -- [PERSISTENCE] Initialize the global database if it is undefined
    if not _G.slcDB then 
        _G.slcDB = {
            showBiS = 1,          -- Default: Enabled
            showOnlyMyClass = 0   -- Default: Disabled
        }
    else
        -- [VALIDATION] Ensure integrity of existing keys
        if _G.slcDB.showBiS == nil then _G.slcDB.showBiS = 1 end
        if _G.slcDB.showOnlyMyClass == nil then _G.slcDB.showOnlyMyClass = 0 end
    end
    Logger:Log("Configuration module initialized.")
end

function ConfigManager:GetState(key)
    if _G.slcDB and _G.slcDB[key] ~= nil then
        return _G.slcDB[key]
    end
    return 0 -- Fail safe return
end


-- SUBSYSTEM: TEXTURE & ASSET CALCULATOR

local AssetEngine = {}

-- texture stringindividual class files
function AssetEngine:GenerateTextureString(className)
    if not className then return "" end

    local texturePath = string_format("%s%s", ASSET_ROOT_PATH, className:lower())
    
    return string_format(
        "|T%s:%d:%d|t",
        texturePath,
        RENDER_CONFIG.DISPLAY_SIZE,
        RENDER_CONFIG.DISPLAY_SIZE
    )
end


-- SUBSYSTEM: TOOLTIP RENDERER

local TooltipRenderer = {}

function TooltipRenderer:ProcessItem(tooltipRef)
    -- [GUARD] Sanity check on the tooltip object
    if not tooltipRef or tooltipRef:IsForbidden() then return end

    -- [QUERY] Retrieve item information from the tooltip instance
    local linkName, linkString = tooltipRef:GetItem()
    
    if not linkString then return end -- No item present

    -- [PARSE] Extract unique Item ID from the Hyperlink string
    local itemID = string_match(linkString, "item:(%d+)")
    
    -- [LOOKUP] Check if this item exists in our registry
    if not itemID or not sliccNote.Items[itemID] then return end

    -- [STATE CHECK] Verify if the user wants to see BiS info
    if ConfigManager:GetState("showBiS") == 0 then return end

    -- Begin rendering process
    self:DrawTooltipLines(tooltipRef, itemID)
end

function TooltipRenderer:DrawTooltipLines(targetTooltip, itemID)
    local itemDataMap = sliccNote.Items[itemID]
    local _, playerClassStr = UnitClass("player")
    local filterByClass = (ConfigManager:GetState("showOnlyMyClass") == 1)
    
    local hasRenderedHeader = false
    local theme = RENDER_CONFIG.HEADER_COLOR

    -- Iterate through all registered BiS entries for this item
    for uniqueKey, phaseValue in pairs(itemDataMap) do
        local bisRecord = sliccNote.BIS[uniqueKey]

        if bisRecord and bisRecord.class then
            local normalizedClass = string.upper(bisRecord.class)
            
            -- [LOGIC] Determine visibility based on user settings
            local shouldDisplay = true
            if filterByClass and (normalizedClass ~= playerClassStr) then
                shouldDisplay = false
            end

            if shouldDisplay then
                -- Fetch Blizzard standard class colors
                local classColor = RAID_CLASS_COLORS[normalizedClass]

                if classColor then
                    -- [UI] Inject Header (Once per item)
                    if not hasRenderedHeader then
                        targetTooltip:AddLine(" ") -- Spacing
						local tq_r, tq_g, tq_b = 0, 1, 0.82
						targetTooltip:AddDoubleLine(
							"AtlasLootTBC Phase 1 BiS for",    -- Left side
							"Rank:",                           -- Right side
							theme.r, theme.g, theme.b,         -- Left side color
							tq_r, tq_g, tq_b		           -- Right side color
						)
							
                        hasRenderedHeader = true
                    end

                    -- [GRAPHICS] Generate the icon string from custom media
                    local iconString = AssetEngine:GenerateTextureString(normalizedClass)

                    -- [TEXT] Build the description string
                    local specStr = bisRecord.spec or ""
                    local commentStr = bisRecord.comment or ""
                    --local displayLine = string_format("%s %s %s %s", iconString, bisRecord.class, specStr, commentStr) --MAYBE revert, fuck it for now
					local displayLine = string_format("%s %s %s", iconString, specStr, commentStr) --only spec names

                    -- [RENDER] Add the double line to the tooltip
                    targetTooltip:AddDoubleLine(
                        displayLine, 
                        phaseValue, 
                        classColor.r, classColor.g, classColor.b, -- Left Color
                        classColor.r, classColor.g, classColor.b  -- Right Color
                    )
                end
            end
        end
    end

    -- Force UI update to accommodate new lines
    targetTooltip:Show()
end

--[[
    API: RECslot
    Desc: Maps an item ID to a registered BiS entry and assigns a phase value.
    Updated: Abstracted data injection logic.
]]
function sliccNote:RECslot(configurationObj, targetItemId, tierValue)
    -- Enclose operations in a local scope to isolate logic
    do
        -- 1. Acquire a pointer to the central item repository
        local registryRoot = self.Items

        -- 2. Resolve the specific container for this Item ID
        -- If the container does not exist, initialize a new table structure
        local itemContainer = registryRoot[targetItemId]
        
        if (itemContainer == nil) then
            itemContainer = {}
            registryRoot[targetItemId] = itemContainer
        end

        -- 3. Extract the unique hash key from the provided configuration object
        local entryHash = configurationObj["ID"]

        -- 4. Commit the tier data to the resolved container
        if entryHash then
            itemContainer[entryHash] = tierValue
        end
    end
end

-- SYSTEM: LIFECYCLE & HOOKS

local SystemCore = CreateFrame("Frame", ADDON_NAME .. "_CoreFrame")

-- List of tooltips to intercept
local TARGET_TOOLTIPS = {
    "GameTooltip",
    "ItemRefTooltip",
    "ShoppingTooltip1",
    "ShoppingTooltip2"
}

-- Safe hook implementation
local function InstallHooks()
    for _, tooltipName in ipairs(TARGET_TOOLTIPS) do
        local tooltipObject = _G[tooltipName]
        if tooltipObject and tooltipObject.HookScript then
            tooltipObject:HookScript("OnTooltipSetItem", function(self)
                -- Wrap in protected call to prevent UI tainting crashes
                local status, err = pcall(function() 
                    TooltipRenderer:ProcessItem(self) 
                end)
                if not status then Logger:Log("Render Error: " .. tostring(err)) end
            end)
        end
    end
end

-- Event Handler
SystemCore:RegisterEvent("PLAYER_ENTERING_WORLD")
SystemCore:SetScript("OnEvent", function(self, event, ...)
    if event == "PLAYER_ENTERING_WORLD" then
        self:UnregisterEvent("PLAYER_ENTERING_WORLD")
        
        -- Boot Sequence
        ConfigManager:Initialize()
        InstallHooks()
        
        Logger:Log("System hooks established.")
    end
end)


-- PUBLIC API (ATLAS INTEGRATION POINTS)


--[[
    API: RegisterBIS
    Desc: Creates a definition entry for a specific class/spec configuration.
    Returns: The constructed entry object.
]]
function sliccNote:RegisterBIS(className, specName, commentText)
    -- Normalize inputs
    local safeClass = className
    local safeSpec = specName or ""
    local safeComment = commentText or ""
    
    -- Create Data Object
    local dataObject = {
        class = safeClass,
        spec = safeSpec,
        comment = safeComment
    }
    
    -- Generate deterministic unique ID
    dataObject.ID = string_format("%s%s%s", dataObject.class, dataObject.spec, dataObject.comment)
    
    -- Persist to global store
    sliccNote.BIS[dataObject.ID] = dataObject
    
    return dataObject
end