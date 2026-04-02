use std::collections::HashMap;

use regex::Regex;

// ---------------------------------------------------------------------------
// Faction names
// ---------------------------------------------------------------------------

pub const FACTION_NAMES: &[&str] = &[
    "Honor Hold",
    "Thrallmar",
    "Cenarion Expedition",
    "Lower City",
    "The Sha'tar",
    "The Aldor",
    "The Scryers",
    "Keepers of Time",
    "Kurenai",
    "The Mag'har",
    "Sporeggar",
    "The Consortium",
    "Ashtongue Deathsworn",
    "The Violet Eye",
    "The Scale of the Sands",
    "Shattered Sun Offensive",
];

// ---------------------------------------------------------------------------
// Dungeon name aliases (WowTBC -> canonical)
// ---------------------------------------------------------------------------

pub const DUNGEON_NAME_ALIASES: &[(&str, &str)] = &[
    ("Steamvaults", "The Steamvault"),
    ("Arcatraz", "The Arcatraz"),
    ("Botanica", "The Botanica"),
    ("Mechanar", "The Mechanar"),
    ("Underbog", "The Underbog"),
    ("Slave Pens", "The Slave Pens"),
    ("Ramparts", "Hellfire Ramparts"),
    ("Shattered Halls", "The Shattered Halls"),
    ("Mana Tombs", "Mana-Tombs"),
    ("Black Morass", "The Black Morass"),
];

// ---------------------------------------------------------------------------
// Raid keywords
// ---------------------------------------------------------------------------

const RAID_KEYWORDS: &[&str] = &[
    "karazhan",
    "gruul",
    "magtheridon",
    "serpentshrine",
    "ssc",
    "tempest keep",
    "hyjal",
    "black temple",
    "sunwell",
    "zul'aman",
];

// ---------------------------------------------------------------------------
// Profession keywords
// ---------------------------------------------------------------------------

const PROFESSION_KEYWORDS: &[(&str, &str)] = &[
    ("tailoring", "Tailoring"),
    ("mooncloth tailoring", "Tailoring"),
    ("leatherworking", "Leatherworking"),
    ("tribal leatherworking", "Leatherworking"),
    ("dragonscale leatherworking", "Leatherworking"),
    ("blacksmithing", "Blacksmithing"),
    ("engineering", "Engineering"),
    ("jewelcrafting", "Jewelcrafting"),
    ("alchemy", "Alchemy"),
    ("enchanting", "Enchanting"),
    ("profession:", "Crafted"),
];

const CLASSIC_RAIDS: &[&str] = &[
    "naxxramas",
    "blackwing lair",
    "aq40",
    "aq20",
    "molten core",
    "temple of ahn'qiraj",
    "ruins of ahn'qiraj",
];

/// All known dungeon names (canonical + aliases).
fn all_dungeon_names(dungeon_reputation: &HashMap<String, String>) -> Vec<String> {
    let mut names: Vec<String> = dungeon_reputation.keys().cloned().collect();
    for &(alias, _) in DUNGEON_NAME_ALIASES {
        names.push(alias.to_string());
    }
    names
}

// ---------------------------------------------------------------------------
// classify_source
// ---------------------------------------------------------------------------

/// Return tags like "dungeon", "heroic", "reputation", "profession", etc.
pub fn classify_source(source: &str, dungeon_reputation: &HashMap<String, String>) -> Vec<String> {
    let s = source.to_lowercase();

    if s.contains("world drop") {
        return vec!["world_drop".to_string()];
    }
    if s.contains("world boss") {
        return vec!["world_boss".to_string()];
    }
    if s.contains("classic -") || s.contains("classic\u{2014}") {
        return vec!["classic".to_string()];
    }
    if s.contains("other (classic") {
        return vec!["classic".to_string()];
    }
    if CLASSIC_RAIDS.iter().any(|cr| s.contains(cr)) {
        return vec!["classic".to_string()];
    }
    if s.contains("arena") || s.contains("pvp") || s.contains("gladiator") {
        return vec!["pvp".to_string()];
    }
    for &(kw, prof_name) in PROFESSION_KEYWORDS {
        if s.contains(kw) {
            return vec!["profession".to_string(), format!("profession:{prof_name}")];
        }
    }

    let mut tags: Vec<String> = Vec::new();

    // Check for reputation
    for &faction in FACTION_NAMES {
        if s.contains(&faction.to_lowercase()) {
            tags.push("reputation".to_string());
            break;
        }
    }
    if !tags.contains(&"reputation".to_string())
        && (s.contains("exalted") || s.contains("revered") || s.contains("honored"))
    {
        tags.push("reputation".to_string());
    }

    // Heroic detection — only when not already classified as reputation
    if !tags.contains(&"reputation".to_string())
        && (s.contains("heroic") || s.contains("(h)") || s.contains("(hc)"))
    {
        tags.push("heroic".to_string());
        if !tags.contains(&"dungeon".to_string()) {
            tags.push("dungeon".to_string());
        }
    }

    if s.contains("drop:") {
        if !RAID_KEYWORDS.iter().any(|rk| s.contains(rk)) {
            if !tags.contains(&"dungeon".to_string()) {
                tags.push("dungeon".to_string());
            }
        } else {
            tags.push("raid".to_string());
        }
    }

    // Detect WowTBC-format sources lacking "Drop:" prefix
    if !tags.contains(&"dungeon".to_string())
        && !tags.contains(&"raid".to_string())
        && !tags.contains(&"reputation".to_string())
    {
        let all_names = all_dungeon_names(dungeon_reputation);
        let mut found_dungeon = false;
        for dname in &all_names {
            if s.contains(&dname.to_lowercase()) {
                tags.push("dungeon".to_string());
                found_dungeon = true;
                break;
            }
        }
        if !found_dungeon {
            for rk in RAID_KEYWORDS {
                if s.contains(rk) {
                    tags.push("raid".to_string());
                    break;
                }
            }
        }
    }

    if s.contains("quest:") || s.contains("quest reward") {
        tags.push("quest".to_string());
    }
    if s.contains("badge of justice")
        || s.contains("badges of justice")
        || s.split('(')
            .last()
            .map_or(false, |part| part.contains("badges"))
    {
        tags.push("badges".to_string());
    }
    if s.contains("vendor:")
        && !tags.contains(&"reputation".to_string())
        && !tags.contains(&"badges".to_string())
    {
        tags.push("vendor".to_string());
    }

    if tags.is_empty() {
        tags.push("other".to_string());
    }
    tags
}

// ---------------------------------------------------------------------------
// extract_faction
// ---------------------------------------------------------------------------

pub fn extract_faction(source: &str) -> Option<String> {
    let s_lower = source.to_lowercase();
    for &faction in FACTION_NAMES {
        if s_lower.contains(&faction.to_lowercase()) {
            return Some(faction.to_string());
        }
    }
    None
}

// ---------------------------------------------------------------------------
// extract_dungeon
// ---------------------------------------------------------------------------

pub fn extract_dungeon(
    source: &str,
    dungeon_reputation: &HashMap<String, String>,
) -> Option<String> {
    // Build a lookup that also matches without "The " prefix and via aliases
    let mut name_map: HashMap<String, String> = HashMap::new();
    for key in dungeon_reputation.keys() {
        name_map.insert(key.clone(), key.clone());
        if let Some(stripped) = key.strip_prefix("The ") {
            name_map.insert(stripped.to_string(), key.clone());
        }
    }
    for &(alias, canonical) in DUNGEON_NAME_ALIASES {
        if dungeon_reputation.contains_key(canonical) {
            name_map.insert(alias.to_string(), canonical.to_string());
        }
    }

    // Try last parenthesized group first
    let paren_re = Regex::new(r"\(([^)]+)\)").expect("invariant: valid regex");
    let parens: Vec<String> = paren_re
        .captures_iter(source)
        .map(|c| c[1].to_string())
        .collect();
    for name in parens.iter().rev() {
        if let Some(canonical) = name_map.get(name.as_str()) {
            return Some(canonical.clone());
        }
    }

    // Also try "Heroic Instance" prefix stripping
    let heroic_re = Regex::new(r"\((?:Heroic\s+)?(.+?)\)").expect("invariant: valid regex");
    if let Some(caps) = heroic_re.captures(source) {
        let name = &caps[1];
        if let Some(canonical) = name_map.get(name) {
            return Some(canonical.clone());
        }
    }

    // Fallback: check if any known dungeon name appears anywhere in the source
    let s_lower = source.to_lowercase();
    for (map_name, canonical) in &name_map {
        if s_lower.contains(&map_name.to_lowercase()) {
            return Some(canonical.clone());
        }
    }

    None
}
