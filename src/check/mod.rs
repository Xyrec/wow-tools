mod analysis;
mod bis_merge;
mod classify;
mod output;
mod soft_reserve;

use std::collections::{HashMap, HashSet};

use anyhow::{Context, Result};

use crate::common;
use crate::common::types::BisItem;

use analysis::{AnalysisContext, categorize_equipped};
use bis_merge::merge_bis_sources;
use output::{
    print_dungeon_priority, print_equipped_section, print_no_upgrade, print_raid_upgrades,
    print_rep_goals, print_slot_breakdown, print_summary,
};
use soft_reserve::load_soft_reserves;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Map character slot names to BiS JSON slot keys.
const SLOT_MAP: &[(&str, &str)] = &[
    ("Head", "head"),
    ("Neck", "neck"),
    ("Shoulder", "shoulders"),
    ("Back", "back"),
    ("Chest", "chest"),
    ("Wrist", "wrists"),
    ("Hands", "hands"),
    ("Waist", "waist"),
    ("Legs", "legs"),
    ("Feet", "feet"),
    ("Finger 1", "rings"),
    ("Finger 2", "rings"),
    ("Trinket 1", "trinkets"),
    ("Trinket 2", "trinkets"),
    ("Main Hand", "weapons"),
    ("Off Hand", "offhands"),
    ("Ranged", "totems"),
];

fn slot_map_lookup(slot_name: &str) -> Option<&'static str> {
    SLOT_MAP
        .iter()
        .find(|(k, _)| *k == slot_name)
        .map(|(_, v)| *v)
}

/// Preferred armor type per spec (looked up from spec registry).
fn preferred_armor(spec: &str) -> &'static str {
    crate::common::specs::find_spec(spec)
        .map(|s| s.armor_type)
        .unwrap_or("Mail")
}

/// Default character file per spec: `{slug}.json`.
fn default_char_file(spec: &str) -> String {
    format!("{spec}.json")
}

// ---------------------------------------------------------------------------
// Item database
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct ItemInfo {
    pub item_id: u32,
    pub name: String,
    pub item_level: u32,
    pub quality: String,
    pub subclass: String,
}

fn load_item_db(root: &std::path::Path) -> HashMap<u32, ItemInfo> {
    let items_path = root.join("sources").join("wowsims-tbc").join("items.json");
    let content = match std::fs::read_to_string(&items_path) {
        Ok(c) => c,
        Err(_) => return HashMap::new(),
    };
    let items: Vec<serde_json::Value> = match serde_json::from_str(&content) {
        Ok(v) => v,
        Err(_) => return HashMap::new(),
    };
    let mut result = HashMap::new();
    for item in items {
        let id = item.get("id").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
        if id == 0 {
            continue;
        }
        let name = item
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let ilvl = item.get("ilvl").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
        let quality = item
            .get("quality")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let armor_type = item
            .get("armor_type")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        result.insert(
            id,
            ItemInfo {
                item_id: id,
                name,
                item_level: ilvl,
                quality,
                subclass: armor_type,
            },
        );
    }
    result
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

pub fn format_ilvl_quality(info: Option<&ItemInfo>) -> String {
    match info {
        Some(i) if i.item_level > 0 => format!("ilvl {} {}", i.item_level, i.quality),
        _ => String::new(),
    }
}

pub fn format_armor_warning(info: Option<&ItemInfo>, pref_armor: &str) -> String {
    match info {
        Some(i) => {
            let sc = &i.subclass;
            if (sc == "Cloth" || sc == "Leather" || sc == "Mail" || sc == "Plate")
                && sc != pref_armor
            {
                format!(" [{sc}]")
            } else {
                String::new()
            }
        }
        None => String::new(),
    }
}

pub fn format_item_extras(info: Option<&ItemInfo>) -> String {
    let iq = format_ilvl_quality(info);
    if iq.is_empty() {
        String::new()
    } else {
        format!("  ({iq})")
    }
}

/// Convert "phase-1" to "Phase 1".
pub fn pretty_phase(phase_key: &str) -> String {
    if let Some(rest) = phase_key.strip_prefix("phase-") {
        format!("Phase {rest}")
    } else {
        phase_key.to_string()
    }
}

/// Comma-separated thousands formatting for integers.
pub fn comma_format(n: i64) -> String {
    if n < 0 {
        return format!("-{}", comma_format(-n));
    }
    let s = n.to_string();
    let bytes = s.as_bytes();
    let len = bytes.len();
    let mut result = String::with_capacity(len + len / 3);
    for (i, &b) in bytes.iter().enumerate() {
        if i > 0 && (len - i) % 3 == 0 {
            result.push(',');
        }
        result.push(b as char);
    }
    result
}

/// Clean up item names that have embedded newlines/whitespace from parsing.
pub fn sanitize_name(name: &str) -> String {
    name.split('\n')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join(" / ")
}

// ---------------------------------------------------------------------------
// Reputation helpers
// ---------------------------------------------------------------------------

const REP_STANDING_ORDER: &[&str] = &[
    "Hated",
    "Hostile",
    "Unfriendly",
    "Neutral",
    "Friendly",
    "Honored",
    "Revered",
    "Exalted",
];

const REP_STANDING_THRESHOLDS: &[(&str, u32)] = &[
    ("Hated", 36000),
    ("Hostile", 3000),
    ("Unfriendly", 3000),
    ("Neutral", 3000),
    ("Friendly", 6000),
    ("Honored", 12000),
    ("Revered", 21000),
    ("Exalted", 999),
];

fn rep_threshold(standing: &str) -> u32 {
    REP_STANDING_THRESHOLDS
        .iter()
        .find(|(s, _)| *s == standing)
        .map(|(_, t)| *t)
        .unwrap_or(0)
}

fn standing_index(standing: &str) -> Option<usize> {
    REP_STANDING_ORDER.iter().position(|s| *s == standing)
}

pub fn calc_rep_to_standing(
    current_standing: &str,
    current_remaining: u32,
    target_standing: &str,
) -> Option<i64> {
    let cur_idx = standing_index(current_standing)?;
    let tgt_idx = standing_index(target_standing)?;
    if cur_idx >= tgt_idx {
        return Some(0);
    }
    let mut total = current_remaining as i64;
    for i in (cur_idx + 1)..tgt_idx {
        total += rep_threshold(REP_STANDING_ORDER[i]) as i64;
    }
    Some(total)
}

pub fn extract_required_standing(source: &str) -> Option<&'static str> {
    let s = source.to_lowercase();
    if s.contains("exalted") {
        Some("Exalted")
    } else if s.contains("revered") {
        Some("Revered")
    } else if s.contains("honored") {
        Some("Honored")
    } else {
        None
    }
}

pub fn format_rep_progress(rep_info: Option<&RepInfo>, required_standing: Option<&str>) -> String {
    let (Some(ri), Some(req)) = (rep_info, required_standing) else {
        return String::new();
    };
    let total = calc_rep_to_standing(&ri.standing, ri.remaining_rep, req);
    match total {
        Some(t) if t > 0 => format!("  -- need {req}, ~{} rep to go", comma_format(t)),
        Some(0) => format!("  -- need {req}, READY TO BUY"),
        _ => String::new(),
    }
}

// ---------------------------------------------------------------------------
// Rep info
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct RepInfo {
    pub name: String,
    pub standing: String,
    pub current_rep: u32,
    pub required_rep: u32,
    pub remaining_rep: u32,
}

// ---------------------------------------------------------------------------
// Dungeon reputation mapping
// ---------------------------------------------------------------------------

pub fn build_dungeon_reputation(
    rep_lookup: &HashMap<String, RepInfo>,
    race: &str,
) -> HashMap<String, String> {
    let mut result: HashMap<String, String> = HashMap::new();

    // Neutral dungeons
    for &(d, f) in &[
        ("The Slave Pens", "Cenarion Expedition"),
        ("The Underbog", "Cenarion Expedition"),
        ("The Steamvault", "Cenarion Expedition"),
        ("Mana-Tombs", "The Consortium"),
        ("Auchenai Crypts", "Lower City"),
        ("Sethekk Halls", "Lower City"),
        ("Shadow Labyrinth", "Lower City"),
        ("Old Hillsbrad Foothills", "Keepers of Time"),
        ("The Black Morass", "Keepers of Time"),
        ("The Mechanar", "The Sha'tar"),
        ("The Botanica", "The Sha'tar"),
        ("The Arcatraz", "The Sha'tar"),
    ] {
        result.insert(d.to_string(), f.to_string());
    }

    let alliance_races = ["Human", "Dwarf", "Night Elf", "Gnome", "Draenei"];
    let horde_races = ["Orc", "Undead", "Tauren", "Troll", "Blood Elf"];

    if rep_lookup.contains_key("Honor Hold") || alliance_races.contains(&race) {
        for &(d, f) in &[
            ("The Blood Furnace", "Honor Hold"),
            ("Hellfire Ramparts", "Honor Hold"),
            ("The Shattered Halls", "Honor Hold"),
        ] {
            result.insert(d.to_string(), f.to_string());
        }
    } else if rep_lookup.contains_key("Thrallmar") || horde_races.contains(&race) {
        for &(d, f) in &[
            ("The Blood Furnace", "Thrallmar"),
            ("Hellfire Ramparts", "Thrallmar"),
            ("The Shattered Halls", "Thrallmar"),
        ] {
            result.insert(d.to_string(), f.to_string());
        }
    } else {
        // Unknown faction — include both
        for &(d, f) in &[
            ("The Blood Furnace", "Honor Hold"),
            ("Hellfire Ramparts", "Honor Hold"),
            ("The Shattered Halls", "Honor Hold"),
        ] {
            result.insert(d.to_string(), f.to_string());
        }
        for &(d, f) in &[
            ("The Blood Furnace", "Thrallmar"),
            ("Hellfire Ramparts", "Thrallmar"),
            ("The Shattered Halls", "Thrallmar"),
        ] {
            result.insert(d.to_string(), f.to_string());
        }
    }

    result
}

// ---------------------------------------------------------------------------
// Upgrade type
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Upgrade {
    pub name: String,
    pub item_id: u32,
    pub rank: String,
    pub phase: String,
    pub phase0_only: bool,
    pub next_phase_rank: Option<String>,
    pub source: String,
    pub tags: Vec<String>,
    pub faction: Option<String>,
    pub rep_info: Option<RepInfo>,
    pub required_standing: Option<&'static str>,
    pub dungeon: Option<String>,
    pub slot: String,
    pub current_item: String,
    pub current_rank: String,
    pub score: f64,
    pub item_info: Option<ItemInfo>,
    pub current_item_info: Option<ItemInfo>,
}

/// Format rank with Phase 0 only marker and future-phase longevity note.
pub fn format_rank_tag(up: &Upgrade) -> String {
    let p0 = if up.phase0_only {
        " [Phase 0 only]"
    } else {
        ""
    };
    let future = match &up.next_phase_rank {
        Some(r) => format!(" + Future Phase {r}"),
        None => String::new(),
    };
    format!("{}{p0}{future}", up.rank)
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

pub fn run(
    spec_raw: &str,
    file: Option<&str>,
    show_crafted: bool,
    include_old_phases: bool,
) -> Result<()> {
    let spec = common::resolve_spec(spec_raw)?;
    let root = common::project_root()?;
    let pref_armor = preferred_armor(spec);

    // Determine character file
    let char_path = match file {
        Some(f) => f.to_string(),
        None => {
            let default = default_char_file(spec);
            let full = root.join("data").join(default);
            full.to_string_lossy().to_string()
        }
    };

    // Load item database
    let item_db = load_item_db(&root);
    let name_resolver: HashMap<u32, String> = item_db
        .iter()
        .map(|(&id, info)| (id, info.name.clone()))
        .collect();

    // Load character
    let character = common::character::load_character(&char_path, &root, Some(&name_resolver))
        .context("failed to load character")?;

    if character.equipped_items.is_empty() {
        anyhow::bail!(
            "No character data for {spec}. Paste your character export into data/{spec}.json"
        );
    }

    // Build rep lookup
    let mut rep_lookup: HashMap<String, RepInfo> = HashMap::new();
    for group in &character.reputations {
        for faction in &group.factions {
            rep_lookup.insert(
                faction.name.clone(),
                RepInfo {
                    name: faction.name.clone(),
                    standing: faction.standing.clone(),
                    current_rep: faction.current_rep,
                    required_rep: faction.required_rep,
                    remaining_rep: faction.remaining_rep,
                },
            );
        }
    }

    // Build dungeon reputation mapping
    let dungeon_reputation = build_dungeon_reputation(&rep_lookup, &character.race);

    // Load soft-reserve config
    let sr_path = root.join("data").join("soft-reserves.txt");
    let (sr_counts, sr_groups) = load_soft_reserves(Some(&sr_path))?;

    // Load and merge BiS data
    let bis_data = merge_bis_sources(spec, &root)?;

    // Determine phases
    let current_phase = common::load_current_phase(&root)?.unwrap_or_else(|| "phase-0".to_string());
    let phases_to_check: Vec<String> = if current_phase == "phase-0" || include_old_phases {
        // Include phase-0 as fallback when explicitly requested or when it IS the current phase
        if current_phase != "phase-0" {
            vec!["phase-0".to_string(), current_phase.clone()]
        } else {
            vec!["phase-0".to_string()]
        }
    } else {
        // Default: only check the current phase
        vec![current_phase.clone()]
    };

    let current_phase_data: HashMap<String, Vec<BisItem>> =
        bis_data.get(&current_phase).cloned().unwrap_or_default();
    let phase0_data: HashMap<String, Vec<BisItem>> = if include_old_phases {
        bis_data.get("phase-0").cloned().unwrap_or_default()
    } else {
        HashMap::new()
    };

    // Build equipped lookup by bis_slot
    let mut equipped_by_slot: Vec<(String, Vec<EquippedSlotItem>)> = Vec::new();
    let mut slot_order: Vec<String> = Vec::new();

    for item in &character.equipped_items {
        if let Some(bis_slot) = slot_map_lookup(&item.slot_name) {
            let esi = EquippedSlotItem {
                item_id: item.item_id,
                item_name: item.item_name.clone(),
                slot_name: item.slot_name.clone(),
            };
            if let Some(entry) = equipped_by_slot.iter_mut().find(|(s, _)| s == bis_slot) {
                entry.1.push(esi);
            } else {
                slot_order.push(bis_slot.to_string());
                equipped_by_slot.push((bis_slot.to_string(), vec![esi]));
            }
        }
    }

    let all_equipped_ids: HashSet<u32> =
        character.equipped_items.iter().map(|i| i.item_id).collect();

    // Categorize equipped items and find upgrades
    let ctx = AnalysisContext {
        bis_data: &bis_data,
        current_phase: &current_phase,
        current_phase_data: &current_phase_data,
        phase0_data: &phase0_data,
        phases_to_check: &phases_to_check,
        dungeon_reputation: &dungeon_reputation,
        rep_lookup: &rep_lookup,
        item_db: &item_db,
        all_equipped_ids: &all_equipped_ids,
        preferred_armor: pref_armor,
        show_crafted,
    };

    let cats = categorize_equipped(&equipped_by_slot, &ctx);

    // Split upgrades into dungeon/rep/badge vs raid
    let dungeon_upgrades_all: Vec<&Upgrade> = cats
        .all_upgrades
        .iter()
        .filter(|u| !u.tags.contains(&"raid".to_string()))
        .collect();
    let raid_upgrades_all: Vec<&Upgrade> = cats
        .all_upgrades
        .iter()
        .filter(|u| u.tags.contains(&"raid".to_string()))
        .collect();

    // Deduplicate ring/trinket upgrades for scoring
    let mut scored_item_ids: HashSet<u32> = HashSet::new();
    let mut deduped_upgrades: Vec<&Upgrade> = Vec::new();
    for up in &dungeon_upgrades_all {
        if scored_item_ids.insert(up.item_id) {
            deduped_upgrades.push(up);
        }
    }

    // Collect reputation needs (deduplicated)
    let mut rep_needs: HashMap<String, Vec<&Upgrade>> = HashMap::new();
    let mut rep_needs_seen: HashMap<String, HashSet<u32>> = HashMap::new();
    for up in &deduped_upgrades {
        if up.tags.contains(&"reputation".to_string()) {
            if let Some(faction) = &up.faction {
                let seen = rep_needs_seen.entry(faction.clone()).or_default();
                if seen.insert(up.item_id) {
                    rep_needs.entry(faction.clone()).or_default().push(up);
                }
            }
        }
    }

    // Compute badge bonus
    let badge_items: Vec<&&Upgrade> = deduped_upgrades
        .iter()
        .filter(|u| u.tags.contains(&"badges".to_string()))
        .collect();
    let badge_bonus = if badge_items.is_empty() {
        0
    } else {
        (badge_items.iter().map(|b| b.score).sum::<f64>() * 0.1).round() as i64
    };

    // Build priority lists
    let sorted_dungeons = analysis::build_dungeon_priority(
        &deduped_upgrades,
        &dungeon_reputation,
        &rep_needs,
        &rep_lookup,
        badge_bonus,
    );
    let sorted_rep = analysis::build_rep_actions(&rep_needs, &rep_lookup, &dungeon_reputation);

    // --- Output ---
    let cp = pretty_phase(&current_phase);
    let phase_list: Vec<String> = phases_to_check.iter().map(|p| pretty_phase(p)).collect();
    println!(
        "Character: {} ({}) -- Checking against: {}",
        character.name,
        character.class,
        phase_list.join(", ")
    );
    if include_old_phases {
        println!("   Current phase: {cp} (authoritative) | Phase 0 (fallback)\n");
    } else {
        println!("   Current phase: {cp}\n");
    }

    print_equipped_section(
        &format!("{} BIS (you're set)", cp.to_uppercase()),
        &cats.current_bis,
        None,
    );
    print_equipped_section(
        &format!(
            "{} OPTIONAL (upgrade available this phase)",
            cp.to_uppercase()
        ),
        &cats.current_option,
        None,
    );

    if !cats.old_bis.is_empty() || !cats.old_option.is_empty() {
        let mut combined = cats.old_bis.clone();
        combined.extend(cats.old_option.iter().cloned());
        let old_bis_set: HashSet<(String, String)> = cats
            .old_bis
            .iter()
            .map(|e| (e.0.clone(), e.1.clone()))
            .collect();
        print_equipped_section(
            &format!("PHASE 0 ONLY (not in {cp} list -- outdated)"),
            &combined,
            Some(&|slot: &str, name: &str| -> String {
                if old_bis_set.contains(&(slot.to_string(), name.to_string())) {
                    "  [was Phase 0 BiS]".to_string()
                } else {
                    "  [was Phase 0 Optional]".to_string()
                }
            }),
        );
    }

    print_equipped_section("NOT ON ANY BIS LIST", &cats.not_listed, None);

    print_dungeon_priority(&sorted_dungeons, &rep_lookup, pref_armor);
    print_rep_goals(&sorted_rep, &rep_lookup, &dungeon_reputation, pref_armor);
    print_slot_breakdown(&dungeon_upgrades_all, pref_armor);
    print_raid_upgrades(&raid_upgrades_all, &sr_counts, &sr_groups, pref_armor);
    print_no_upgrade(&cats.no_upgrade);
    print_summary(
        &cp,
        &cats.current_bis,
        &cats.current_option,
        &cats.old_bis,
        &cats.old_option,
        &cats.not_listed,
        &dungeon_upgrades_all,
        &raid_upgrades_all,
        &cats.no_upgrade,
    );

    Ok(())
}

#[derive(Debug, Clone)]
pub struct EquippedSlotItem {
    pub item_id: u32,
    pub item_name: String,
    pub slot_name: String,
}
