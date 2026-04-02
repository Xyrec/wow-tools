use std::collections::HashMap;
use std::path::Path;

use anyhow::{Result, bail};

use crate::common::types::BisItem;

/// Rank priority: lower is better.
fn rank_priority(rank: &str) -> u32 {
    match rank {
        "BiS" => 0,
        "Optional" | "Option" => 1,
        "Alternative" => 2,
        _ => 9,
    }
}

const PRIMARY_SOURCES: &[&str] = &["al_bis_gear.json", "wtbc_bis_gear.json"];
const SECONDARY_SOURCES: &[&str] = &["iv_bis_gear.json"];

/// Load and merge BiS data from all sources for a spec.
///
/// Primary sources (AL, WTBC) preserve their BiS/Optional ranks.
/// Secondary sources (IV, WH) have all ranks downgraded to Alternative.
/// If an item appears in multiple sources, the best rank wins.
///
/// Returns: phase_key -> slot_key -> Vec<BisItem>
pub fn merge_bis_sources(
    spec: &str,
    root: &Path,
) -> Result<HashMap<String, HashMap<String, Vec<BisItem>>>> {
    let output_dir = root.join("output").join(spec);
    let mut phases: HashMap<String, HashMap<String, Vec<BisItem>>> = HashMap::new();

    let all_sources: Vec<&str> = PRIMARY_SOURCES
        .iter()
        .chain(SECONDARY_SOURCES.iter())
        .copied()
        .collect();

    for src_name in &all_sources {
        let src_path = output_dir.join(src_name);
        if !src_path.exists() {
            continue;
        }
        let is_secondary = SECONDARY_SOURCES.contains(src_name);
        let content = std::fs::read_to_string(&src_path)?;
        let src_data: serde_json::Value = serde_json::from_str(&content)?;

        let Some(phase_map) = src_data.get("phases").and_then(|p| p.as_object()) else {
            continue;
        };

        for (phase_key, phase_slots) in phase_map {
            let Some(slots_obj) = phase_slots.as_object() else {
                continue;
            };

            let phase_entry = phases.entry(phase_key.clone()).or_default();

            for (slot_key, items_val) in slots_obj {
                let Some(items_arr) = items_val.as_array() else {
                    continue;
                };

                let slot_entry = phase_entry.entry(slot_key.clone()).or_default();

                // Build a lookup for O(1) by item_id
                let mut seen: HashMap<u32, usize> = HashMap::new();
                for (i, item) in slot_entry.iter().enumerate() {
                    if item.item_id != 0 {
                        seen.insert(item.item_id, i);
                    }
                }

                for item_val in items_arr {
                    let item: BisItem = match serde_json::from_value(item_val.clone()) {
                        Ok(i) => i,
                        Err(_) => continue,
                    };

                    let mut effective_rank = item.rank.clone();
                    if is_secondary {
                        effective_rank = "Alternative".to_string();
                    }
                    if effective_rank == "Option" {
                        effective_rank = "Optional".to_string();
                    }

                    let iid = item.item_id;
                    if iid != 0 {
                        if let Some(&idx) = seen.get(&iid) {
                            let existing_rank = &slot_entry[idx].rank;
                            if rank_priority(&effective_rank) < rank_priority(existing_rank) {
                                slot_entry[idx].rank = effective_rank;
                            }
                        } else {
                            let mut merged = item;
                            merged.rank = effective_rank;
                            seen.insert(iid, slot_entry.len());
                            slot_entry.push(merged);
                        }
                    } else {
                        let mut merged = item;
                        merged.rank = effective_rank;
                        slot_entry.push(merged);
                    }
                }
            }
        }
    }

    if phases.is_empty() {
        bail!(
            "No BiS data found in {}. Expected al_bis_gear.json or wtbc_bis_gear.json.",
            output_dir.display()
        );
    }

    Ok(phases)
}
