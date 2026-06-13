use std::collections::{HashMap, HashSet};

use super::analysis::{DungeonEntry, EquippedDisplay, RepAction};
use super::soft_reserve::{match_raid_tag, raid_tag_pretty_name};
use super::{
    RepInfo, Upgrade, comma_format, format_armor_warning, format_item_extras, format_rank_tag,
    format_rep_progress,
};

// ---------------------------------------------------------------------------
// Equipped sections
// ---------------------------------------------------------------------------

pub fn print_equipped_section(
    title: &str,
    items: &[EquippedDisplay],
    suffix_fn: Option<&dyn Fn(&str, &str) -> String>,
) {
    if items.is_empty() {
        return;
    }
    println!("=== {title} ===");
    for (slot, name, armor, extras) in items {
        let suffix = match suffix_fn {
            Some(f) => f(slot, name),
            None => String::new(),
        };
        println!("  {:<12}  {name}{armor}{extras}{suffix}", slot);
    }
    println!();
}

// ---------------------------------------------------------------------------
// Dungeon priority
// ---------------------------------------------------------------------------

pub fn print_dungeon_priority(
    sorted_dungeons: &[DungeonEntry],
    rep_lookup: &HashMap<String, RepInfo>,
    preferred_armor: &str,
) {
    if sorted_dungeons.is_empty() {
        return;
    }
    println!("=== PRIORITY: DUNGEONS TO RUN (ranked by value per run) ===");
    for (i, entry) in sorted_dungeons.iter().enumerate() {
        let badge_tag = if entry.badges { " +badges" } else { "" };
        let rep_tag = if let Some(ref faction) = entry.rep_faction {
            if let Some(ri) = rep_lookup.get(faction) {
                format!(
                    " +{faction} rep (You: {}, {} to next tier)",
                    ri.standing,
                    comma_format(ri.remaining_rep as i64)
                )
            } else {
                format!(" +{faction} rep")
            }
        } else {
            String::new()
        };

        println!(
            "\n  #{}  {}  (score: {:.0}){badge_tag}{rep_tag}",
            i + 1,
            entry.key,
            entry.score
        );
        println!("       Score: {}", entry.score_breakdown.join(" | "));

        for drop in &entry.drops {
            let rank_tag = format_rank_tag(drop);
            let armor = format_armor_warning(drop.item_info.as_ref(), preferred_armor);
            let extra = format_item_extras(drop.item_info.as_ref());
            let cur_extra = format_item_extras(drop.current_item_info.as_ref());
            println!(
                "       [{:<16}]  {}{armor}{extra}  ({} -- replaces {}{})",
                rank_tag, drop.name, drop.slot, drop.current_item, cur_extra
            );
        }

        if !entry.rep_vendor_items.is_empty() {
            println!("       Also earns rep toward:");
            for vi in &entry.rep_vendor_items {
                let rank_tag = format_rank_tag(vi);
                let armor = format_armor_warning(vi.item_info.as_ref(), preferred_armor);
                let extra = format_item_extras(vi.item_info.as_ref());
                println!(
                    "         [{:<16}]  {}{armor}{extra}  ({})",
                    rank_tag, vi.name, vi.slot
                );
            }
        }
    }
    println!();
}

// ---------------------------------------------------------------------------
// Reputation goals
// ---------------------------------------------------------------------------

pub fn print_rep_goals(
    sorted_rep: &[RepAction],
    rep_lookup: &HashMap<String, RepInfo>,
    dungeon_reputation: &HashMap<String, String>,
    preferred_armor: &str,
) {
    if sorted_rep.is_empty() {
        return;
    }
    // Suppress the entire section if there's no actual rep_info
    let _ = (rep_lookup, dungeon_reputation);
    println!("=== REPUTATION GOALS ===");
    for entry in sorted_rep {
        let ri = &entry.rep_info;
        println!(
            "\n  {}  (You: {}, {} rep to next tier)",
            entry.faction,
            ri.standing,
            comma_format(ri.remaining_rep as i64)
        );
        for item in &entry.items {
            let rank_tag = format_rank_tag(item);
            let armor = format_armor_warning(item.item_info.as_ref(), preferred_armor);
            let extra = format_item_extras(item.item_info.as_ref());
            let rep_prog = format_rep_progress(Some(&entry.rep_info), item.required_standing);
            println!(
                "    [{:<16}]  {}{armor}{extra}  ({} -- replaces {}){rep_prog}",
                rank_tag, item.name, item.slot, item.current_item
            );
        }
        if !entry.dungeons_for_rep.is_empty() {
            println!("    Grind via: {}", entry.dungeons_for_rep.join(", "));
        }
    }
    println!();
}

// ---------------------------------------------------------------------------
// All upgrades by slot
// ---------------------------------------------------------------------------

pub fn print_slot_breakdown(all_upgrades: &[&Upgrade], preferred_armor: &str) {
    if all_upgrades.is_empty() {
        return;
    }

    // Group by slot, preserving order of first occurrence. Dedup by item_id
    // within each slot so paired empty slots (two rings/trinkets) don't list
    // the same upgrade twice.
    let mut slot_order: Vec<String> = Vec::new();
    let mut slot_groups: HashMap<String, Vec<&Upgrade>> = HashMap::new();
    let mut seen_per_slot: HashMap<String, HashSet<u32>> = HashMap::new();
    for up in all_upgrades {
        if !seen_per_slot.entry(up.slot.clone()).or_default().insert(up.item_id) {
            continue;
        }
        if !slot_groups.contains_key(&up.slot) {
            slot_order.push(up.slot.clone());
        }
        slot_groups.entry(up.slot.clone()).or_default().push(up);
    }

    println!("=== ALL UPGRADES BY SLOT ===");
    for slot in &slot_order {
        let items_in_slot = &slot_groups[slot];
        let first = items_in_slot[0];
        let current = &first.current_item;
        let current_rank = &first.current_rank;
        let cur_armor = format_armor_warning(first.current_item_info.as_ref(), preferred_armor);
        let cur_extra = format_item_extras(first.current_item_info.as_ref());
        let rank_note = if current_rank != "Not on list" {
            format!(" [{current_rank}]")
        } else {
            String::new()
        };
        println!("\n  {slot}: {current}{cur_armor}{rank_note}{cur_extra}");

        for up in items_in_slot {
            let heroic = if up.tags.contains(&"heroic".to_string()) {
                " (H)"
            } else {
                ""
            };
            let rank_label = format!("[{}]", format_rank_tag(up));
            let armor = format_armor_warning(up.item_info.as_ref(), preferred_armor);
            let extra = format_item_extras(up.item_info.as_ref());
            let mut line = format!(
                "    {:<18} {}{armor}{extra}{heroic}  --  {}",
                rank_label, up.name, up.source
            );
            if let Some(ref ri) = up.rep_info {
                let rep_prog = format_rep_progress(Some(ri), up.required_standing);
                if !rep_prog.is_empty() {
                    line += &format!(
                        "  ({})",
                        rep_prog
                            .trim_start_matches(" -")
                            .trim_start_matches("- ")
                            .trim()
                    );
                } else {
                    line += &format!(
                        "  (You: {} -- {} rep to next tier)",
                        ri.standing,
                        comma_format(ri.remaining_rep as i64)
                    );
                }
            }
            println!("{line}");
        }
    }
    println!();
}

// ---------------------------------------------------------------------------
// Raid upgrades
// ---------------------------------------------------------------------------

pub fn print_raid_upgrades(
    raid_upgrades: &[&Upgrade],
    sr_counts: &HashMap<String, i32>,
    sr_groups: &HashMap<String, String>,
    preferred_armor: &str,
) {
    if raid_upgrades.is_empty() {
        return;
    }

    // Group by SR group key
    let mut group_order: Vec<String> = Vec::new();
    let mut group_items: HashMap<String, Vec<&Upgrade>> = HashMap::new();
    for up in raid_upgrades {
        let tag = match_raid_tag(&up.source);
        let group_key = if let Some(ref t) = tag {
            sr_groups.get(t).cloned().unwrap_or_else(|| t.clone())
        } else {
            "unknown".to_string()
        };
        if !group_items.contains_key(&group_key) {
            group_order.push(group_key.clone());
        }
        group_items.entry(group_key).or_default().push(up);
    }

    // Deduplicate within each group
    let mut seen_ids: HashSet<u32> = HashSet::new();
    for group_key in &group_order {
        let items = group_items
            .get_mut(group_key)
            .expect("invariant: key exists in map");
        let mut deduped: Vec<&Upgrade> = Vec::new();
        for up in items.iter() {
            if seen_ids.insert(up.item_id) {
                deduped.push(up);
            }
        }
        *items = deduped;
    }

    // Emit unknown-source warnings
    if let Some(unknowns) = group_items.get("unknown") {
        for up in unknowns {
            eprintln!("WARNING: unrecognized raid source: {}", up.source);
        }
    }

    println!("=== RAID UPGRADES ===");
    for group_key in &group_order {
        let items = group_items
            .get_mut(group_key)
            .expect("invariant: key exists");
        if items.is_empty() {
            continue;
        }

        if group_key == "unknown" {
            println!("\n  Unknown Raid  (SR: unknown)");
            items.sort_by(|a, b| {
                b.score
                    .partial_cmp(&a.score)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });
            for up in items.iter() {
                let rank_label = format!("[{}]", format_rank_tag(up));
                let armor = format_armor_warning(up.item_info.as_ref(), preferred_armor);
                let extra = format_item_extras(up.item_info.as_ref());
                println!(
                    "    {:<18} {}{armor}{extra}  ({} -- replaces {})  --  {}",
                    rank_label, up.name, up.slot, up.current_item, up.source
                );
            }
            continue;
        }

        // Build pretty header from group key
        let tags: Vec<&str> = group_key.split('+').map(|t| t.trim()).collect();
        let pretty_names: Vec<&str> = tags.iter().map(|t| raid_tag_pretty_name(t)).collect();
        let header = pretty_names.join(" + ");

        // SR info from the first tag
        let sr_count = sr_counts.get(tags[0]).copied().unwrap_or(0);
        let sr_label = if sr_count == 0 {
            "master looter".to_string()
        } else if sr_count == 1 {
            "1 soft reserve".to_string()
        } else {
            format!("{sr_count} soft reserves")
        };

        println!("\n  {header}  ({sr_label})");

        items.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        for up in items.iter() {
            let rank_label = format!("[{}]", format_rank_tag(up));
            let armor = format_armor_warning(up.item_info.as_ref(), preferred_armor);
            let extra = format_item_extras(up.item_info.as_ref());
            println!(
                "    {:<18} {}{armor}{extra}  ({} -- replaces {})  --  {}",
                rank_label, up.name, up.slot, up.current_item, up.source
            );
        }
    }
    println!();
}

// ---------------------------------------------------------------------------
// No upgrade slots
// ---------------------------------------------------------------------------

pub fn print_empty_slots(empty_slots: &[EquippedDisplay]) {
    if empty_slots.is_empty() {
        return;
    }
    println!("=== EMPTY SLOTS (nothing equipped -- anything is an upgrade) ===");
    for (slot, _name, _armor, _extras) in empty_slots {
        println!("  {slot}");
    }
    println!();
}

pub fn print_no_upgrade(no_upgrade_slots: &[EquippedDisplay]) {
    if no_upgrade_slots.is_empty() {
        return;
    }
    println!("=== NO DUNGEON/REP/RAID UPGRADE (craft or world boss needed) ===");
    for (slot, name, rank, extras) in no_upgrade_slots {
        println!("  {:<12}  {name} [{rank}]{extras}", slot);
    }
    println!();
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

pub fn print_summary(
    cp: &str,
    current_bis: &[EquippedDisplay],
    current_option: &[EquippedDisplay],
    old_bis: &[EquippedDisplay],
    old_option: &[EquippedDisplay],
    not_listed: &[EquippedDisplay],
    empty: &[EquippedDisplay],
    dungeon_upgrades: &[&Upgrade],
    raid_upgrades: &[&Upgrade],
    no_upgrade_slots: &[EquippedDisplay],
) {
    let dungeon_slot_count = if dungeon_upgrades.is_empty() {
        0
    } else {
        let slots: HashSet<&str> = dungeon_upgrades.iter().map(|u| u.slot.as_str()).collect();
        slots.len()
    };
    let raid_slot_count = if raid_upgrades.is_empty() {
        0
    } else {
        let slots: HashSet<&str> = raid_upgrades.iter().map(|u| u.slot.as_str()).collect();
        slots.len()
    };
    let total = current_bis.len()
        + current_option.len()
        + old_bis.len()
        + old_option.len()
        + not_listed.len()
        + empty.len();
    println!("Summary: {total} slots total");
    println!("  {cp} BiS: {}", current_bis.len());
    println!("  {cp} Optional: {}", current_option.len());
    if !empty.is_empty() {
        println!("  Empty (need anything): {}", empty.len());
    }
    if !old_bis.is_empty() || !old_option.is_empty() {
        println!(
            "  Phase 0 only (outdated): {}",
            old_bis.len() + old_option.len()
        );
    }
    if !not_listed.is_empty() {
        println!("  Not on any list: {}", not_listed.len());
    }
    if dungeon_slot_count > 0 {
        println!("  Slots with dungeon/rep upgrades: {dungeon_slot_count}");
    }
    if raid_slot_count > 0 {
        println!("  Slots with raid upgrades: {raid_slot_count}");
    }
    if !no_upgrade_slots.is_empty() {
        println!("  Slots needing craft/other: {}", no_upgrade_slots.len());
    }
}
