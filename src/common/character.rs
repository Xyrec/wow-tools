use std::collections::HashMap;
use std::io::Read;
use std::path::Path;

use anyhow::{Context, Result};
use serde_json::Value;

use super::WSE_SLOT_ORDER;
use super::types::{Character, EquippedItem, ReputationGroup};

/// Load character JSON from `path` (or `"-"` for stdin).
///
/// Handles both the WowSims Exporter (WSE) format and the classic
/// `{"character": {...}}` format.
pub fn load_character(
    path: &str,
    project_root: &Path,
    item_name_resolver: Option<&HashMap<u32, String>>,
) -> Result<Character> {
    let data: Value = if path == "-" {
        let mut buf = String::new();
        std::io::stdin()
            .read_to_string(&mut buf)
            .context("failed to read stdin")?;
        serde_json::from_str(&buf).context("invalid JSON on stdin")?
    } else {
        let p = Path::new(path);
        let resolved = if p.exists() {
            p.to_path_buf()
        } else {
            let alt = project_root
                .join("data")
                .join(p.file_name().unwrap_or(p.as_ref()));
            if alt.exists() { alt } else { p.to_path_buf() }
        };
        let content = std::fs::read_to_string(&resolved)
            .with_context(|| format!("failed to read {}", resolved.display()))?;
        serde_json::from_str(&content)
            .with_context(|| format!("invalid JSON in {}", resolved.display()))?
    };

    // Detect WSE format (has gear.items)
    if data.get("gear").and_then(|g| g.get("items")).is_some() {
        return normalize_wse(&data, item_name_resolver);
    }

    // Classic format - may or may not have a "character" wrapper
    let char_data = if data.get("character").is_some() {
        &data["character"]
    } else {
        &data
    };

    parse_classic_character(char_data)
}

fn parse_classic_character(v: &Value) -> Result<Character> {
    let equipped_items = v
        .get("equippedItems")
        .and_then(|e| e.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|item| {
                    Some(EquippedItem {
                        slot: item.get("slot")?.as_u64()? as u32,
                        slot_name: item.get("slotName")?.as_str()?.to_string(),
                        item_id: item.get("itemId")?.as_u64()? as u32,
                        item_name: item.get("itemName")?.as_str()?.to_string(),
                    })
                })
                .collect()
        })
        .unwrap_or_default();

    let reputations: Vec<ReputationGroup> = v
        .get("reputations")
        .map(|r| serde_json::from_value(r.clone()).unwrap_or_default())
        .unwrap_or_default();

    Ok(Character {
        name: v
            .get("name")
            .and_then(|n| n.as_str())
            .unwrap_or("Unknown")
            .to_string(),
        class: v
            .get("class")
            .and_then(|c| c.as_str())
            .unwrap_or("")
            .to_string(),
        race: v
            .get("race")
            .and_then(|r| r.as_str())
            .unwrap_or("")
            .to_string(),
        talents: v
            .get("talents")
            .and_then(|t| t.as_str())
            .unwrap_or("")
            .to_string(),
        equipped_items,
        reputations,
        wse_raw: None,
    })
}

fn normalize_wse(
    data: &Value,
    item_name_resolver: Option<&HashMap<u32, String>>,
) -> Result<Character> {
    let items = data["gear"]["items"]
        .as_array()
        .context("WSE gear.items is not an array")?;

    let mut equipped = Vec::new();
    for (i, item) in items.iter().enumerate() {
        if i >= WSE_SLOT_ORDER.len() {
            continue;
        }
        let slot_name = WSE_SLOT_ORDER[i].to_string();
        let item_id = if item.is_null() {
            0
        } else {
            item.get("id").and_then(|id| id.as_u64()).unwrap_or(0) as u32
        };

        // An empty slot (null entry or missing id) is recorded with item_id 0
        // and name "(empty)" so the checker can recommend gear for it -
        // anything in that slot's BiS list is an upgrade over nothing.
        if item_id == 0 {
            equipped.push(EquippedItem {
                slot: (i + 1) as u32,
                slot_name,
                item_id: 0,
                item_name: "(empty)".to_string(),
            });
            continue;
        }

        let name = item_name_resolver
            .and_then(|r| r.get(&item_id))
            .cloned()
            .unwrap_or_else(|| format!("ID:{item_id}"));

        equipped.push(EquippedItem {
            slot: (i + 1) as u32,
            slot_name,
            item_id,
            item_name: name,
        });
    }

    Ok(Character {
        name: data
            .get("name")
            .and_then(|n| n.as_str())
            .unwrap_or("Unknown")
            .to_string(),
        class: data
            .get("class")
            .and_then(|c| c.as_str())
            .unwrap_or("")
            .to_string(),
        race: data
            .get("race")
            .and_then(|r| r.as_str())
            .unwrap_or("")
            .to_string(),
        talents: data
            .get("talents")
            .and_then(|t| t.as_str())
            .unwrap_or("")
            .to_string(),
        equipped_items: equipped,
        reputations: vec![],
        wse_raw: Some(data.clone()),
    })
}
