use std::collections::{HashMap, HashSet};

use crate::common::types::BisItem;

use super::classify::{classify_source, extract_dungeon, extract_faction};
use super::{
    EquippedSlotItem, ItemInfo, RepInfo, Upgrade, extract_required_standing, format_rank_tag,
    sanitize_name,
};

// ---------------------------------------------------------------------------
// Rank scores & scoring
// ---------------------------------------------------------------------------

fn rank_base_score(rank: &str) -> f64 {
    match rank {
        "BiS" => 100.0,
        "Optional" => 75.0,
        "Alternative" => 50.0,
        _ => 50.0,
    }
}

fn score_upgrade(
    rank: &str,
    phase: &str,
    current_phase: &str,
    next_phase_rank: Option<&str>,
) -> f64 {
    let cur_num: i32 = current_phase
        .split('-')
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    let item_num: i32 = phase
        .split('-')
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);

    let phases_behind = (cur_num - item_num).max(0) as u32;
    let decay = 0.5_f64.powi(phases_behind as i32);

    let base = rank_base_score(rank);
    let mut score = base * decay;

    match next_phase_rank {
        Some("BiS") => score += 50.0,
        Some("Optional" | "Option") => score += 30.0,
        _ => {}
    }

    score
}

// ---------------------------------------------------------------------------
// Slot resolution
// ---------------------------------------------------------------------------

fn resolve_slot_key<'a>(bis_slot: &str, phase_data: &HashMap<String, Vec<BisItem>>) -> String {
    if phase_data.contains_key(bis_slot) {
        return bis_slot.to_string();
    }
    // Relic slot
    if bis_slot == "totems" || bis_slot == "idols" || bis_slot == "librams" {
        for alt in &["totems", "idols", "librams"] {
            if phase_data.contains_key(*alt) {
                return alt.to_string();
            }
        }
    }
    // Off-hand slot
    if bis_slot == "offhands" || bis_slot == "shields-offhands" || bis_slot == "shields" {
        for alt in &["offhands", "shields-offhands", "shields"] {
            if phase_data.contains_key(*alt) {
                return alt.to_string();
            }
        }
    }
    // Shoulder slot
    if bis_slot == "shoulders" || bis_slot == "shoulder" {
        for alt in &["shoulders", "shoulder"] {
            if phase_data.contains_key(*alt) {
                return alt.to_string();
            }
        }
    }
    bis_slot.to_string()
}

fn lookup_item_rank(
    item_id: u32,
    bis_slot: &str,
    phase_data: &HashMap<String, Vec<BisItem>>,
) -> Option<String> {
    let slot_key = resolve_slot_key(bis_slot, phase_data);
    if let Some(items) = phase_data.get(&slot_key) {
        for item in items {
            if item.item_id == item_id {
                return Some(item.rank.clone());
            }
        }
    }
    None
}

/// Determine an item's effective rank using phase priority.
fn get_effective_rank(
    item_id: u32,
    bis_slot: &str,
    current_phase_data: &HashMap<String, Vec<BisItem>>,
    phase0_data: &HashMap<String, Vec<BisItem>>,
    current_phase: &str,
) -> (Option<String>, Option<String>, bool) {
    if current_phase != "phase-0" {
        if let Some(rank) = lookup_item_rank(item_id, bis_slot, current_phase_data) {
            return (Some(rank), Some(current_phase.to_string()), false);
        }
    }

    if let Some(rank) = lookup_item_rank(item_id, bis_slot, phase0_data) {
        let p0_only = current_phase != "phase-0";
        return (Some(rank), Some("phase-0".to_string()), p0_only);
    }

    (None, None, false)
}

// ---------------------------------------------------------------------------
// Analysis context & categories
// ---------------------------------------------------------------------------

pub struct AnalysisContext<'a> {
    pub bis_data: &'a HashMap<String, HashMap<String, Vec<BisItem>>>,
    pub current_phase: &'a str,
    pub current_phase_data: &'a HashMap<String, Vec<BisItem>>,
    pub phase0_data: &'a HashMap<String, Vec<BisItem>>,
    pub phases_to_check: &'a [String],
    pub dungeon_reputation: &'a HashMap<String, String>,
    pub rep_lookup: &'a HashMap<String, RepInfo>,
    pub item_db: &'a HashMap<u32, ItemInfo>,
    pub all_equipped_ids: &'a HashSet<u32>,
    pub preferred_armor: &'a str,
    pub show_crafted: bool,
}

/// Equipped display tuple: (slot_label, name, armor_warning, extras)
pub type EquippedDisplay = (String, String, String, String);

pub struct EquippedCategories {
    pub current_bis: Vec<EquippedDisplay>,
    pub current_option: Vec<EquippedDisplay>,
    pub old_bis: Vec<EquippedDisplay>,
    pub old_option: Vec<EquippedDisplay>,
    pub not_listed: Vec<EquippedDisplay>,
    /// Slots with nothing equipped — every BiS item is an upgrade.
    pub empty: Vec<EquippedDisplay>,
    pub all_upgrades: Vec<Upgrade>,
    pub no_upgrade: Vec<EquippedDisplay>,
}

// ---------------------------------------------------------------------------
// Core analysis
// ---------------------------------------------------------------------------

pub fn categorize_equipped(
    equipped_by_slot: &[(String, Vec<EquippedSlotItem>)],
    ctx: &AnalysisContext,
) -> EquippedCategories {
    let mut result = EquippedCategories {
        current_bis: Vec::new(),
        current_option: Vec::new(),
        old_bis: Vec::new(),
        old_option: Vec::new(),
        not_listed: Vec::new(),
        empty: Vec::new(),
        all_upgrades: Vec::new(),
        no_upgrade: Vec::new(),
    };

    for (bis_slot, items) in equipped_by_slot {
        for eq_item in items {
            let item_id = eq_item.item_id;
            let item_name = &eq_item.item_name;
            let slot_label = &eq_item.slot_name;

            let eq_info = ctx.item_db.get(&item_id);
            let eq_extras = super::format_item_extras(eq_info);
            let eq_armor = super::format_armor_warning(eq_info, ctx.preferred_armor);
            let eq_display: EquippedDisplay =
                (slot_label.clone(), item_name.clone(), eq_armor, eq_extras);

            // Empty slot (item_id 0): every item in this slot's BiS list is an
            // upgrade over an empty slot. No equipped position to compare, so
            // find_slot_upgrades lists the whole slot.
            if item_id == 0 {
                result.empty.push(eq_display);
                let slot_upgrades =
                    find_slot_upgrades(bis_slot, slot_label, 0, item_name, None, None, ctx);
                result.all_upgrades.extend(slot_upgrades);
                continue;
            }

            let (eq_rank, _eq_phase, eq_p0_only) = get_effective_rank(
                item_id,
                bis_slot,
                ctx.current_phase_data,
                ctx.phase0_data,
                ctx.current_phase,
            );

            // Classify into tier
            match eq_rank.as_deref() {
                Some("BiS") if !eq_p0_only => {
                    result.current_bis.push(eq_display.clone());
                }
                Some("Option" | "Optional" | "Alternative") if !eq_p0_only => {
                    result.current_option.push(eq_display.clone());
                }
                Some("BiS") if eq_p0_only => {
                    result.old_bis.push(eq_display.clone());
                }
                Some("Option" | "Optional" | "Alternative") if eq_p0_only => {
                    result.old_option.push(eq_display.clone());
                }
                Some("PvP") => {
                    if eq_p0_only {
                        result.old_option.push(eq_display.clone());
                    } else {
                        result.current_option.push(eq_display.clone());
                    }
                }
                _ => {
                    result.not_listed.push(eq_display.clone());
                }
            }

            let slot_upgrades = find_slot_upgrades(
                bis_slot,
                slot_label,
                item_id,
                item_name,
                eq_rank.as_deref(),
                eq_info,
                ctx,
            );
            if slot_upgrades.is_empty() {
                let rank_str = eq_rank.as_deref().unwrap_or("Not on list");
                result.no_upgrade.push((
                    slot_label.clone(),
                    item_name.clone(),
                    rank_str.to_string(),
                    super::format_item_extras(eq_info),
                ));
            }
            result.all_upgrades.extend(slot_upgrades);
        }
    }

    result
}

fn find_slot_upgrades(
    bis_slot: &str,
    slot_label: &str,
    item_id: u32,
    item_name: &str,
    eq_rank: Option<&str>,
    eq_info: Option<&ItemInfo>,
    ctx: &AnalysisContext,
) -> Vec<Upgrade> {
    let mut slot_upgrades: Vec<Upgrade> = Vec::new();
    let mut seen_item_ids: HashSet<u32> = HashSet::new();

    for phase in ctx.phases_to_check {
        let phase_data = match ctx.bis_data.get(phase.as_str()) {
            Some(d) => d,
            None => continue,
        };
        let slot_key = resolve_slot_key(bis_slot, phase_data);
        let slot_items = match phase_data.get(&slot_key) {
            Some(items) => items,
            None => continue,
        };

        // Find the equipped item's position in this slot's list
        let equipped_pos = slot_items.iter().position(|si| si.item_id == item_id);

        for (idx, bis_item) in slot_items.iter().enumerate() {
            let bis_id = bis_item.item_id;
            if bis_id == item_id || !seen_item_ids.insert(bis_id) {
                continue;
            }
            if ctx.all_equipped_ids.contains(&bis_id) {
                // Remove from seen so it can be re-checked in another phase
                seen_item_ids.remove(&bis_id);
                continue;
            }

            // Skip items ranked lower than equipped, unless equipped is BiS
            if let Some(eq_pos) = equipped_pos {
                if idx >= eq_pos && eq_rank != Some("BiS") {
                    continue;
                }
            }

            let (up_rank, up_phase, up_p0_only) = get_effective_rank(
                bis_id,
                bis_slot,
                ctx.current_phase_data,
                ctx.phase0_data,
                ctx.current_phase,
            );
            let Some(up_rank) = up_rank else {
                continue;
            };

            // When equipped is BiS, only show other BiS items (not downgrades)
            if eq_rank == Some("BiS") {
                if let Some(eq_pos) = equipped_pos {
                    if idx >= eq_pos && up_rank != "BiS" {
                        continue;
                    }
                }
            }

            let source = &bis_item.source;
            let tags = classify_source(source, ctx.dungeon_reputation);

            if tags.contains(&"classic".to_string()) {
                continue;
            }
            if !ctx.show_crafted && tags.contains(&"profession".to_string()) {
                continue;
            }

            let faction = extract_faction(source);

            // Skip rep items from the opposing faction
            if let Some(ref fac) = faction {
                if tags.contains(&"reputation".to_string())
                    && (fac == "Thrallmar" || fac == "Honor Hold")
                {
                    let player_hf_faction = ctx.dungeon_reputation.get("Hellfire Ramparts");
                    if player_hf_faction == Some(&"Honor Hold".to_string()) && fac == "Thrallmar" {
                        continue;
                    }
                    if player_hf_faction == Some(&"Thrallmar".to_string()) && fac == "Honor Hold" {
                        continue;
                    }
                }
            }

            let rep_info = faction
                .as_ref()
                .and_then(|f| ctx.rep_lookup.get(f))
                .cloned();
            let dungeon = extract_dungeon(source, ctx.dungeon_reputation);

            // Check next phase for longevity bonus
            let cur_num: i32 = ctx
                .current_phase
                .split('-')
                .nth(1)
                .and_then(|s| s.parse().ok())
                .unwrap_or(0);
            let next_phase_key = format!("phase-{}", cur_num + 1);
            let next_phase_data = ctx.bis_data.get(next_phase_key.as_str());
            let next_phase_rank =
                next_phase_data.and_then(|npd| lookup_item_rank(bis_id, bis_slot, npd));

            let item_score = score_upgrade(
                &up_rank,
                up_phase.as_deref().unwrap_or("phase-0"),
                ctx.current_phase,
                next_phase_rank.as_deref(),
            );
            let required_standing = extract_required_standing(source);

            let upgrade = Upgrade {
                name: sanitize_name(&bis_item.name),
                item_id: bis_id,
                rank: up_rank,
                phase: up_phase.unwrap_or_else(|| "phase-0".to_string()),
                phase0_only: up_p0_only,
                next_phase_rank,
                source: source.clone(),
                tags,
                faction,
                rep_info,
                required_standing,
                dungeon,
                slot: slot_label.to_string(),
                current_item: item_name.to_string(),
                current_rank: eq_rank.unwrap_or("Not on list").to_string(),
                score: item_score,
                item_info: ctx.item_db.get(&bis_id).cloned(),
                current_item_info: eq_info.cloned(),
            };
            slot_upgrades.push(upgrade);
        }
    }

    slot_upgrades
}

// ---------------------------------------------------------------------------
// Dungeon priority
// ---------------------------------------------------------------------------

pub struct DungeonEntry {
    pub key: String,
    pub dungeon: String,
    pub heroic: bool,
    pub drops: Vec<Upgrade>,
    pub score: f64,
    pub score_breakdown: Vec<String>,
    pub rep_faction: Option<String>,
    pub rep_vendor_items: Vec<Upgrade>,
    pub badges: bool,
}

pub fn build_dungeon_priority(
    deduped_upgrades: &[&Upgrade],
    dungeon_reputation: &HashMap<String, String>,
    rep_needs: &HashMap<String, Vec<&Upgrade>>,
    _rep_lookup: &HashMap<String, RepInfo>,
    badge_bonus: i64,
) -> Vec<DungeonEntry> {
    let mut dungeon_actions: HashMap<String, DungeonEntry> = HashMap::new();

    for up in deduped_upgrades {
        if !up.tags.contains(&"dungeon".to_string()) {
            continue;
        }
        let Some(ref dungeon) = up.dungeon else {
            continue;
        };

        let is_heroic = up.tags.contains(&"heroic".to_string());
        let key = if is_heroic {
            format!("Heroic {dungeon}")
        } else {
            dungeon.clone()
        };

        let entry = dungeon_actions
            .entry(key.clone())
            .or_insert_with(|| DungeonEntry {
                key: key.clone(),
                dungeon: dungeon.clone(),
                heroic: is_heroic,
                drops: Vec::new(),
                score: 0.0,
                score_breakdown: Vec::new(),
                rep_faction: dungeon_reputation.get(dungeon.as_str()).cloned(),
                rep_vendor_items: Vec::new(),
                badges: is_heroic,
            });

        entry.drops.push((*up).clone());
        entry.score += up.score;
        entry
            .score_breakdown
            .push(format!("{} drop: +{:.0}", format_rank_tag(up), up.score));
    }

    // Add rep synergy scoring
    let keys: Vec<String> = dungeon_actions.keys().cloned().collect();
    for key in &keys {
        let faction = dungeon_actions[key].rep_faction.clone();
        let badges = dungeon_actions[key].badges;
        if let Some(ref fac) = faction {
            if let Some(items) = rep_needs.get(fac) {
                let rep_score: f64 = items.iter().map(|vi| vi.score).sum();
                let vendor_items: Vec<Upgrade> = items.iter().map(|vi| (*vi).clone()).collect();
                let entry = dungeon_actions.get_mut(key).expect("invariant: key exists");
                entry.rep_vendor_items = vendor_items;
                entry.score += rep_score;
                entry
                    .score_breakdown
                    .push(format!("rep toward {fac} vendor items: +{rep_score:.0}"));
            }
        }
        if badges && badge_bonus > 0 {
            let entry = dungeon_actions.get_mut(key).expect("invariant: key exists");
            entry.score += badge_bonus as f64;
            entry
                .score_breakdown
                .push(format!("badges toward vendor items: +{badge_bonus}"));
        }
    }

    // Merge normal drops into heroic entries, and create heroic entries for normal-only dungeons
    let entry_keys: Vec<String> = dungeon_actions.keys().cloned().collect();
    for key in entry_keys {
        let entry_heroic = dungeon_actions[&key].heroic;
        if entry_heroic {
            continue;
        }
        let heroic_key = format!("Heroic {}", dungeon_actions[&key].dungeon);

        if dungeon_actions.contains_key(&heroic_key) {
            // Merge normal drops into existing heroic entry
            let normal_drops: Vec<Upgrade> = dungeon_actions[&key].drops.clone();
            let heroic_entry = dungeon_actions
                .get_mut(&heroic_key)
                .expect("invariant: key exists");
            let heroic_drop_ids: HashSet<u32> =
                heroic_entry.drops.iter().map(|d| d.item_id).collect();
            for drop in normal_drops {
                if !heroic_drop_ids.contains(&drop.item_id) {
                    heroic_entry.score += drop.score;
                    heroic_entry.score_breakdown.push(format!(
                        "{} drop: +{:.0}",
                        format_rank_tag(&drop),
                        drop.score
                    ));
                    heroic_entry.drops.push(drop);
                }
            }
        } else {
            // No heroic entry — create one if there's rep synergy
            let faction = dungeon_actions[&key].rep_faction.clone();
            if let Some(ref fac) = faction {
                if rep_needs.contains_key(fac) {
                    let normal = &dungeon_actions[&key];
                    let mut heroic_entry = DungeonEntry {
                        key: heroic_key.clone(),
                        dungeon: normal.dungeon.clone(),
                        heroic: true,
                        drops: normal.drops.clone(),
                        score: normal.score + badge_bonus as f64,
                        score_breakdown: normal.score_breakdown.clone(),
                        rep_faction: Some(fac.clone()),
                        rep_vendor_items: normal.rep_vendor_items.clone(),
                        badges: true,
                    };
                    if badge_bonus > 0 {
                        heroic_entry
                            .score_breakdown
                            .push(format!("badges toward vendor items: +{badge_bonus}"));
                    }
                    dungeon_actions.insert(heroic_key, heroic_entry);
                }
            }
        }
    }

    let mut sorted: Vec<DungeonEntry> = dungeon_actions.into_values().collect();
    sorted.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    sorted
}

// ---------------------------------------------------------------------------
// Reputation actions
// ---------------------------------------------------------------------------

pub struct RepAction {
    pub faction: String,
    pub items: Vec<Upgrade>,
    pub rep_info: RepInfo,
    pub dungeons_for_rep: Vec<String>,
    pub score: f64,
}

pub fn build_rep_actions(
    rep_needs: &HashMap<String, Vec<&Upgrade>>,
    rep_lookup: &HashMap<String, RepInfo>,
    dungeon_reputation: &HashMap<String, String>,
) -> Vec<RepAction> {
    let mut rep_actions: Vec<RepAction> = Vec::new();

    for (faction, items) in rep_needs {
        let Some(rep_info) = rep_lookup.get(faction) else {
            continue;
        };
        let dungeons_for_rep: Vec<String> = dungeon_reputation
            .iter()
            .filter(|(_, f)| f == &faction)
            .map(|(d, _)| d.clone())
            .collect();
        let total_score: f64 = items.iter().map(|i| i.score).sum();
        rep_actions.push(RepAction {
            faction: faction.clone(),
            items: items.iter().map(|i| (*i).clone()).collect(),
            rep_info: rep_info.clone(),
            dungeons_for_rep,
            score: total_score,
        });
    }

    rep_actions.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    rep_actions
}
