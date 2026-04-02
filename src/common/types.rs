use std::collections::HashMap;

use serde::Deserialize;

// ---------------------------------------------------------------------------
// Character data (classic format with equippedItems)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Character {
    pub name: String,
    pub class: String,
    pub race: String,
    pub talents: String,
    pub equipped_items: Vec<EquippedItem>,
    pub reputations: Vec<ReputationGroup>,
    /// Preserved raw WSE data for gem/enchant parsing.
    pub wse_raw: Option<serde_json::Value>,
}

#[derive(Debug, Clone)]
pub struct EquippedItem {
    pub slot: u32,
    pub slot_name: String,
    pub item_id: u32,
    pub item_name: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ReputationGroup {
    pub group: String,
    pub factions: Vec<Faction>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Faction {
    pub name: String,
    pub standing: String,
    #[serde(default, rename = "currentRep")]
    pub current_rep: u32,
    #[serde(default, rename = "requiredRep")]
    pub required_rep: u32,
    #[serde(default, rename = "remainingRep")]
    pub remaining_rep: u32,
}

// ---------------------------------------------------------------------------
// BiS data (loaded from parser-generated JSON)
// ---------------------------------------------------------------------------

/// Top-level BiS JSON structure from each parser output.
#[derive(Debug, Clone, Deserialize)]
pub struct BisFile {
    pub current_phase: String,
    pub phases: HashMap<String, HashMap<String, Vec<BisItem>>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BisItem {
    pub rank: String,
    pub name: String,
    pub source: String,
    #[serde(default)]
    pub item_id: u32,
}

// ---------------------------------------------------------------------------
// Quality names
// ---------------------------------------------------------------------------

pub fn quality_name(quality: u32) -> &'static str {
    match quality {
        0 => "Poor",
        1 => "Common",
        2 => "Uncommon",
        3 => "Rare",
        4 => "Epic",
        5 => "Legendary",
        _ => "Unknown",
    }
}
