pub mod sources;

use std::collections::HashMap;

use anyhow::{Context, Result};
use rusqlite::Connection;

use crate::common;
use sources::*;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

static STAT_ALIASES: &[(&str, u32)] = &[
    ("defense", 12),
    ("dodge", 13),
    ("parry", 14),
    ("block", 15),
    ("hit", 31),
    ("crit", 32),
    ("haste", 36),
    ("expertise", 37),
    ("resilience", 35),
];

static STAT_TO_WOWSIMS: &[(u32, &str)] = &[
    (12, "Defense"),
    (13, "Dodge"),
    (14, "Parry"),
    (15, "Block"),
    (31, "MeleeHit"),
    (32, "MeleeCrit"),
    (35, "Resilience"),
    (36, "SpellHaste"),
    (37, "Expertise"),
];

const DEFENSE_RATING_PER_SKILL: f64 = 2.3654;
const BASE_DEFENSE_SKILL: f64 = 350.0;
const BOSS_CRIT_PCT: f64 = 5.60;
const DEFENSE_SKILL_PER_PCT: f64 = 25.0;
const RESILIENCE_RATING_PER_PCT: f64 = 39.4231;

static EQUIP_SLOTS: &[(u32, &str)] = &[
    (1, "Head"),
    (2, "Neck"),
    (3, "Shoulder"),
    (5, "Chest"),
    (6, "Waist"),
    (7, "Legs"),
    (8, "Feet"),
    (9, "Wrist"),
    (10, "Hands"),
    (11, "Finger"),
    (12, "Trinket"),
    (13, "One-Hand"),
    (14, "Shield"),
    (16, "Back"),
    (21, "Main Hand"),
    (23, "Held In Off-Hand"),
    (28, "Relic"),
];

static SLOT_ALIASES: &[(&str, &[&str])] = &[
    ("Shield", &["Off Hand"]),
    ("Held In Off-Hand", &["Off Hand"]),
    ("One-Hand", &["Main Hand"]),
    ("Finger", &["Finger 1", "Finger 2"]),
    ("Trinket", &["Trinket 1", "Trinket 2"]),
];

static SLOT_ORDER: &[&str] = &[
    "Head", "Neck", "Shoulder", "Back", "Chest", "Wrist", "Hands", "Waist",
    "Legs", "Feet", "Finger", "Trinket", "Main Hand", "One-Hand", "Shield",
    "Held In Off-Hand", "Relic",
];

static CLASS_BITMASKS: &[(&str, u32)] = &[
    ("Paladin", 2),
    ("Warrior", 1),
    ("Druid", 1024),
    ("Shaman", 64),
    ("Hunter", 4),
    ("Rogue", 8),
    ("Priest", 16),
    ("Mage", 128),
    ("Warlock", 256),
];

static CLASS_ARMOR_TYPE: &[(&str, u32)] = &[
    ("Paladin", 4),
    ("Warrior", 4),
    ("Shaman", 3),
    ("Hunter", 3),
    ("Druid", 2),
    ("Rogue", 2),
    ("Priest", 1),
    ("Mage", 1),
    ("Warlock", 1),
];

static DEFENSE_SKILL_TALENTS: &[(&str, usize, usize, i32)] = &[
    ("paladin", 1, 8, 4), // Anticipation: +4 defense skill per point
];

static QUALITY_NAMES: &[(u32, &str)] = &[
    (0, "Poor"),
    (1, "Common"),
    (2, "Uncommon"),
    (3, "Rare"),
    (4, "Epic"),
    (5, "Legendary"),
];

fn quality_name(q: u32) -> &'static str {
    QUALITY_NAMES
        .iter()
        .find(|(id, _)| *id == q)
        .map(|(_, n)| *n)
        .unwrap_or("?")
}

fn equip_slot_name(inv_type: u32) -> Option<&'static str> {
    EQUIP_SLOTS
        .iter()
        .find(|(id, _)| *id == inv_type)
        .map(|(_, n)| *n)
}

fn get_talent_defense_skill(char_class: &str, talents: &str) -> i32 {
    if talents.is_empty() {
        return 0;
    }
    let trees: Vec<&str> = talents.split('-').collect();
    let mut total = 0;
    for &(cls, tree_idx, pos, skill_per_pt) in DEFENSE_SKILL_TALENTS {
        if char_class.to_lowercase() != cls {
            continue;
        }
        if tree_idx < trees.len() && pos < trees[tree_idx].len() {
            let points = trees[tree_idx].as_bytes()[pos] - b'0';
            total += points as i32 * skill_per_pt;
        }
    }
    total
}

fn get_wse_bonus_stat(raw_data: &serde_json::Value, wowsims_stat: &str) -> f64 {
    let root = common::project_root().unwrap_or_default();
    let gems_db = load_json_db(&root.join("sources").join("wowsims-tbc").join("gems.json"));
    let enchants_db =
        load_json_db(&root.join("sources").join("wowsims-tbc").join("enchants.json"));

    let mut total = 0.0;
    let items = raw_data
        .get("gear")
        .and_then(|g| g.get("items"))
        .and_then(|i| i.as_array());
    let Some(items) = items else {
        return 0.0;
    };

    for item in items {
        if item.is_null() {
            continue;
        }
        if let Some(gems) = item.get("gems").and_then(|g| g.as_array()) {
            for gem_val in gems {
                let gem_id = gem_val.as_u64().unwrap_or(0) as u32;
                if gem_id != 0 {
                    if let Some(gem) = gems_db.get(&gem_id) {
                        total += gem
                            .get("stats")
                            .and_then(|s| s.get(wowsims_stat))
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0);
                    }
                }
            }
        }
        let enchant_id = item.get("enchant").and_then(|e| e.as_u64()).unwrap_or(0) as u32;
        if enchant_id != 0 {
            if let Some(enc) = enchants_db.get(&enchant_id) {
                total += enc
                    .get("stats")
                    .and_then(|s| s.get(wowsims_stat))
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
            }
        }
    }
    total
}

fn load_json_db(path: &std::path::Path) -> HashMap<u32, serde_json::Value> {
    let Ok(content) = std::fs::read_to_string(path) else {
        return HashMap::new();
    };
    let Ok(items) = serde_json::from_str::<Vec<serde_json::Value>>(&content) else {
        return HashMap::new();
    };
    let mut result = HashMap::new();
    for item in items {
        let key_field = if item.get("effect_id").is_some() {
            "effect_id"
        } else {
            "id"
        };
        if let Some(id) = item.get(key_field).and_then(|i| i.as_u64()) {
            result.insert(id as u32, item);
        }
    }
    result
}

// ---------------------------------------------------------------------------
// Core find-stat logic
// ---------------------------------------------------------------------------

fn find_stat_upgrades(
    conn: &Connection,
    char: &crate::common::types::Character,
    stat_type_id: u32,
    stat_name: &str,
    target: f64,
    source_filter: Option<&str>,
) -> Result<()> {
    let char_class = &char.class;
    let class_bit = CLASS_BITMASKS
        .iter()
        .find(|(c, _)| c.eq_ignore_ascii_case(char_class))
        .map(|(_, b)| *b)
        .unwrap_or(0);
    let max_armor = CLASS_ARMOR_TYPE
        .iter()
        .find(|(c, _)| c.eq_ignore_ascii_case(char_class))
        .map(|(_, a)| *a)
        .unwrap_or(0);
    let max_rep_rank = 5u32; // Honored

    // Build equipped lookup
    let mut equipped_by_slot: HashMap<String, &crate::common::types::EquippedItem> = HashMap::new();
    for eq in &char.equipped_items {
        equipped_by_slot.insert(eq.slot_name.clone(), eq);
    }

    // Current stat values per slot
    let mut current_stats: HashMap<String, i32> = HashMap::new();
    let mut total_current = 0i32;
    for eq in &char.equipped_items {
        let val = get_stat_value(conn, eq.item_id, stat_type_id);
        current_stats.insert(eq.slot_name.clone(), val);
        total_current += val;
    }

    // Gem/enchant bonus from WSE data
    let wowsims_stat = STAT_TO_WOWSIMS
        .iter()
        .find(|(id, _)| *id == stat_type_id)
        .map(|(_, n)| *n)
        .unwrap_or("");
    let gem_enchant_bonus = if let Some(ref wse) = char.wse_raw {
        if !wowsims_stat.is_empty() {
            get_wse_bonus_stat(wse, wowsims_stat)
        } else {
            0.0
        }
    } else {
        0.0
    };
    let total_with_gems = total_current as f64 + gem_enchant_bonus;

    // Talent defense skill
    let talent_defense_skill = if stat_name == "defense" {
        get_talent_defense_skill(&char.class, &char.talents)
    } else {
        0
    };

    // Defense cap analysis
    if stat_name == "defense" && target > 0.0 {
        let base_def = BASE_DEFENSE_SKILL + talent_defense_skill as f64;
        let skill_from_rating = (total_with_gems / DEFENSE_RATING_PER_SKILL).floor();
        let current_defense = base_def + skill_from_rating;

        // Current resilience
        let mut current_resil = 0.0f64;
        if let Some(ref wse) = char.wse_raw {
            current_resil = get_wse_bonus_stat(wse, "Resilience");
        }
        for eq in &char.equipped_items {
            current_resil += get_stat_value(conn, eq.item_id, 35) as f64;
        }

        let def_crit_pct = (current_defense - BASE_DEFENSE_SKILL) / DEFENSE_SKILL_PER_PCT;
        let resil_crit_pct = current_resil / RESILIENCE_RATING_PER_PCT;
        let total_crit_pct = def_crit_pct + resil_crit_pct;
        let remaining_pct = (BOSS_CRIT_PCT - total_crit_pct).max(0.0);

        println!("Crit Cap: {BOSS_CRIT_PCT:.2}% reduction needed");
        println!(
            "  Defense:    {} skill ({} above {} base) = {:.2}%",
            current_defense as i32,
            (current_defense - BASE_DEFENSE_SKILL) as i32,
            BASE_DEFENSE_SKILL as i32,
            def_crit_pct
        );
        if talent_defense_skill > 0 {
            println!(
                "              ({} base + {} talents + {} from {:.0} rating)",
                BASE_DEFENSE_SKILL as i32 - talent_defense_skill,
                talent_defense_skill,
                skill_from_rating as i32,
                total_with_gems
            );
        }
        println!(
            "  Resilience: {:.0} rating = {:.2}%",
            current_resil, resil_crit_pct
        );
        if (BOSS_CRIT_PCT - total_crit_pct).abs() < 0.05 {
            println!(
                "  Total:      {:.4}% / {:.2}%",
                total_crit_pct, BOSS_CRIT_PCT
            );
        } else {
            println!(
                "  Total:      {:.2}% / {:.2}%",
                total_crit_pct, BOSS_CRIT_PCT
            );
        }

        // Empty gem sockets
        let mut empty_sockets: Vec<(String, Vec<String>)> = Vec::new();
        let mut total_empty = 0u32;
        if let Some(ref wse) = char.wse_raw {
            if let Some(items) = wse.get("gear").and_then(|g| g.get("items")).and_then(|i| i.as_array()) {
                for (idx, wse_item) in items.iter().enumerate() {
                    if wse_item.is_null() || idx >= common::WSE_SLOT_ORDER.len() {
                        continue;
                    }
                    let item_id = wse_item.get("id").and_then(|i| i.as_u64()).unwrap_or(0) as u32;
                    if item_id == 0 {
                        continue;
                    }
                    let sockets: Vec<u32> = conn
                        .query_row(
                            "SELECT socketColor_1, socketColor_2, socketColor_3 FROM item_template WHERE entry=?",
                            [item_id],
                            |row| Ok(vec![row.get::<_, u32>(0)?, row.get::<_, u32>(1)?, row.get::<_, u32>(2)?]),
                        )
                        .unwrap_or_default();
                    let socket_colors: Vec<String> = sockets
                        .iter()
                        .filter(|&&c| c != 0)
                        .map(|&c| socket_color_name(c).to_string())
                        .collect();
                    if socket_colors.is_empty() {
                        continue;
                    }
                    let gems_equipped: Vec<u32> = wse_item
                        .get("gems")
                        .and_then(|g| g.as_array())
                        .map(|arr| {
                            arr.iter()
                                .map(|v| v.as_u64().unwrap_or(0) as u32)
                                .collect()
                        })
                        .unwrap_or_default();
                    let mut slot_empties = Vec::new();
                    for (s_idx, color) in socket_colors.iter().enumerate() {
                        let gem_id = gems_equipped.get(s_idx).copied().unwrap_or(0);
                        if gem_id == 0 {
                            slot_empties.push(color.clone());
                            total_empty += 1;
                        }
                    }
                    if !slot_empties.is_empty() {
                        empty_sockets.push((common::WSE_SLOT_ORDER[idx].to_string(), slot_empties));
                    }
                }
            }
        }

        if remaining_pct <= 0.0 {
            println!("  CRIT CAPPED!");
            if total_empty > 0 {
                println!(
                    "\n  ({total_empty} empty gem sockets — cap reached without them)"
                );
            }
            println!();
            return Ok(());
        } else {
            if remaining_pct < 0.01 {
                println!("  Short:      {remaining_pct:.4}%");
            } else {
                println!("  Short:      {remaining_pct:.2}%");
            }
            let def_rating_needed =
                (remaining_pct * DEFENSE_SKILL_PER_PCT * DEFENSE_RATING_PER_SKILL).ceil() as i32;
            let resil_rating_needed =
                (remaining_pct * RESILIENCE_RATING_PER_PCT).ceil() as i32;
            println!(
                "  Need: {def_rating_needed} more defense rating OR {resil_rating_needed} more resilience rating"
            );

            if total_empty > 0 {
                println!("\n  Empty gem sockets ({total_empty} total):");
                for (slot_name, colors) in &empty_sockets {
                    println!("    {slot_name}: {}", colors.join(", "));
                }

                // Gem suggestions
                let root = common::project_root()?;
                let gems_db = load_json_db(&root.join("sources").join("wowsims-tbc").join("gems.json"));
                let mut def_gems: Vec<(String, String, f64, String)> = gems_db
                    .values()
                    .filter_map(|g| {
                        let def_val = g.get("stats")?.get("Defense")?.as_f64()?;
                        if def_val <= 0.0 {
                            return None;
                        }
                        Some((
                            g.get("name")?.as_str()?.to_string(),
                            g.get("color").and_then(|c| c.as_str()).unwrap_or("").to_string(),
                            def_val,
                            g.get("quality").and_then(|q| q.as_str()).unwrap_or("").to_string(),
                        ))
                    })
                    .collect();
                def_gems.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap());
                if !def_gems.is_empty() {
                    let best = &def_gems[0];
                    let cheap = def_gems.iter().find(|g| g.3 == "Uncommon");
                    println!("\n  Gem suggestions:");
                    let gems_to_cap = (def_rating_needed as f64 / best.2).ceil() as i32;
                    println!(
                        "    Best: {} ({}) +{:.0} def - need {} to cap",
                        best.0, best.1, best.2, gems_to_cap
                    );
                    if let Some(cheap) = cheap {
                        if cheap.0 != best.0 {
                            let gems_to_cap_cheap =
                                (def_rating_needed as f64 / cheap.2).ceil() as i32;
                            println!(
                                "    Cheap: {} ({}) +{:.0} def - need {} to cap",
                                cheap.0, cheap.1, cheap.2, gems_to_cap_cheap
                            );
                        }
                    }
                }
            }
        }
    } else {
        println!(
            "Current total {stat_name} rating from gear: {:.0}",
            total_with_gems
        );
        if gem_enchant_bonus > 0.0 {
            println!(
                "  (items: {total_current}, gems/enchants: +{:.0})",
                gem_enchant_bonus
            );
        }
    }
    println!();

    // Find candidate items
    let conditions: String = (1..=10)
        .map(|i| format!("(stat_type{i}={stat_type_id} AND stat_value{i}>0)"))
        .collect::<Vec<_>>()
        .join(" OR ");
    let class_filter = if class_bit > 0 {
        format!("AND (AllowableClass = -1 OR (AllowableClass & {class_bit}) > 0)")
    } else {
        String::new()
    };

    let sql = format!(
        "SELECT entry, name, Quality, ItemLevel, RequiredLevel, InventoryType, \
         bonding, RequiredReputationFaction, RequiredReputationRank, \
         AllowableClass, class, subclass \
         FROM item_template \
         WHERE ({conditions}) \
         AND RequiredLevel <= 70 \
         AND ItemLevel >= 85 \
         AND Quality >= 2 \
         {class_filter} \
         ORDER BY ItemLevel DESC"
    );

    let mut stmt = conn.prepare(&sql)?;
    let rows: Vec<(u32, String, u32, u32, u32, u32, u32, u32, u32, i64, u32, u32)> = stmt
        .query_map([], |row| {
            Ok((
                row.get(0)?,
                row.get(1)?,
                row.get(2)?,
                row.get(3)?,
                row.get(4)?,
                row.get(5)?,
                row.get(6)?,
                row.get(7)?,
                row.get(8)?,
                row.get(9)?,
                row.get(10)?,
                row.get(11)?,
            ))
        })?
        .filter_map(|r| r.ok())
        .collect();

    // Group by slot
    let mut candidates_by_slot: HashMap<String, Vec<CandidateItem>> = HashMap::new();
    for (item_id, name, quality, ilvl, _req_level, inv_type, bonding, rep_faction, rep_rank, _allow_class, item_class, item_subclass) in rows {
        let Some(slot_name) = equip_slot_name(inv_type) else {
            continue;
        };
        let stat_val = get_stat_value(conn, item_id, stat_type_id);
        if stat_val <= 0 {
            continue;
        }
        let item_sources = get_item_sources(conn, item_id);
        let classification = classify_source(bonding, rep_faction, &item_sources);

        // Apply filters
        match source_filter {
            Some("dungeon") if classification != "dungeon" => continue,
            Some("boe") if classification != "boe" => continue,
            Some("rep") if classification != "rep" => continue,
            Some("easy") => match classification {
                "boe" if quality > 3 => continue,
                "rep" if rep_rank > max_rep_rank => continue,
                "dungeon" | "boe" | "rep" => {}
                _ => continue,
            },
            _ => {}
        }

        let armor_tag = if item_class == 4 && max_armor > 0 && (1..=4).contains(&item_subclass) {
            if item_subclass < max_armor {
                format!(" [{}]", armor_subclass_name(item_subclass))
            } else {
                String::new()
            }
        } else {
            String::new()
        };

        candidates_by_slot
            .entry(slot_name.to_string())
            .or_default()
            .push(CandidateItem {
                id: item_id,
                name,
                quality,
                ilvl,
                slot: slot_name.to_string(),
                stat_value: stat_val,
                classification: classification.to_string(),
                rep_faction,
                rep_rank,
                sources: item_sources,
                armor_tag,
            });
    }

    // Print results
    for &slot_name in SLOT_ORDER {
        let candidates = match candidates_by_slot.get(slot_name) {
            Some(c) if !c.is_empty() => c,
            _ => continue,
        };

        let match_slots: Vec<&str> = SLOT_ALIASES
            .iter()
            .find(|(s, _)| *s == slot_name)
            .map(|(_, aliases)| aliases.to_vec())
            .unwrap_or_default();

        let mut equipped_items: Vec<(String, String, i32)> = Vec::new();
        for (eq_slot, eq_data) in &equipped_by_slot {
            if match_slots.contains(&eq_slot.as_str())
                || eq_slot == slot_name
                || eq_slot.starts_with(slot_name)
            {
                let v = get_stat_value(conn, eq_data.item_id, stat_type_id);
                equipped_items.push((eq_slot.clone(), eq_data.item_name.clone(), v));
            }
        }
        if equipped_items.is_empty() {
            equipped_items.push((slot_name.to_string(), "(empty)".to_string(), 0));
        }

        let mut sorted_candidates = candidates.to_vec();
        sorted_candidates.sort_by(|a, b| b.stat_value.cmp(&a.stat_value));

        for (eq_slot, current_name, current_val) in &equipped_items {
            println!(
                "=== {eq_slot} (current: {current_name}, {stat_name}+{current_val}) ==="
            );

            let mut seen = std::collections::HashSet::new();
            let mut shown = 0;
            for c in &sorted_candidates {
                if seen.contains(&c.id) {
                    continue;
                }
                seen.insert(c.id);
                if shown >= 10 {
                    break;
                }
                shown += 1;

                let diff = c.stat_value - current_val;
                let diff_str = if diff > 0 {
                    format!("+{diff}")
                } else {
                    format!("{diff}")
                };
                let qual = quality_name(c.quality);
                let source_str =
                    format_source(conn, &c.classification, c.rep_faction, c.rep_rank, &c.sources);
                let name_with_tag = format!("{}{}", c.name, c.armor_tag);
                println!(
                    "  {:<45} ilvl{:3} {:6} {stat_name}+{:<3} ({:>4})  {}",
                    name_with_tag, c.ilvl, qual, c.stat_value, diff_str, source_str
                );
            }
            println!();
        }
    }

    Ok(())
}

#[derive(Debug, Clone)]
struct CandidateItem {
    id: u32,
    name: String,
    quality: u32,
    ilvl: u32,
    slot: String,
    stat_value: i32,
    classification: String,
    rep_faction: u32,
    rep_rank: u32,
    sources: Vec<ItemSource>,
    armor_tag: String,
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

pub fn run(file: &str, stat: &str, target: f64, source: &str) -> Result<()> {
    let root = common::project_root()?;
    let db = common::db_path(&root);
    if !db.exists() {
        anyhow::bail!(
            "TBC database not found at {}",
            db.display()
        );
    }
    let conn = Connection::open(&db)
        .with_context(|| format!("failed to open database {}", db.display()))?;

    let stat_type_id = STAT_ALIASES
        .iter()
        .find(|(name, _)| *name == stat)
        .map(|(_, id)| *id)
        .context(format!("Unknown stat '{stat}'"))?;

    let source_filter = if source == "all" { None } else { Some(source) };

    // Load character — need item name resolver from wowsims
    let items_path = root.join("sources").join("wowsims-tbc").join("items.json");
    let name_resolver: Option<HashMap<u32, String>> = std::fs::read_to_string(&items_path)
        .ok()
        .and_then(|content| serde_json::from_str::<Vec<serde_json::Value>>(&content).ok())
        .map(|items| {
            items
                .iter()
                .filter_map(|i| {
                    let id = i.get("id")?.as_u64()? as u32;
                    let name = i.get("name")?.as_str()?.to_string();
                    Some((id, name))
                })
                .collect()
        });

    let char = common::character::load_character(
        file,
        &root,
        name_resolver.as_ref(),
    )?;

    println!("Finding {stat} rating upgrades for {}", char.name);
    println!();

    find_stat_upgrades(&conn, &char, stat_type_id, stat, target, source_filter.as_deref())?;

    Ok(())
}
