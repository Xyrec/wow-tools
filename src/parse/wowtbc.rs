use std::collections::HashMap;
use std::path::Path;

use indexmap::IndexMap;

use anyhow::Result;
use scraper::{Html, Selector};

use super::{ParsedItem, ParsedOutput, find_phase_files, write_output};
use crate::common;

/// Map wowtbc slot IDs to canonical slot keys.
fn map_slot(slot_id: &str) -> Option<&'static str> {
    Some(match slot_id {
        "head" => "head",
        "neck" => "neck",
        "shoulder" => "shoulders",
        "back" => "back",
        "chest" => "chest",
        "wrist" => "wrists",
        "hands" => "hands",
        "waist" => "waist",
        "legs" => "legs",
        "feet" => "feet",
        "finger_1" | "finger_2" => "rings",
        "trinket_1" | "trinket_2" => "trinkets",
        "weapon" => "weapons",
        "off_hand" => "offhands",
        "relic" => "totems",
        _ => return None,
    })
}

/// Build name→ID mapping from wowsims items.json.
fn build_name_to_id(root: &Path) -> HashMap<String, u32> {
    let items_path = root.join("sources").join("wowsims-tbc").join("items.json");
    let Ok(content) = std::fs::read_to_string(&items_path) else {
        return HashMap::new();
    };
    let Ok(items) = serde_json::from_str::<Vec<serde_json::Value>>(&content) else {
        return HashMap::new();
    };

    let mut result = HashMap::new();
    for item in &items {
        let Some(name) = item.get("name").and_then(|n| n.as_str()) else {
            continue;
        };
        let Some(id) = item.get("id").and_then(|i| i.as_u64()) else {
            continue;
        };
        let id = id as u32;
        // Store both exact and lowercase; exact takes priority
        let lower = name.to_lowercase();
        result.entry(lower).or_insert(id);
        result.insert(name.to_string(), id);
    }
    result
}

fn parse_phase_file(
    filepath: &Path,
    name_to_id: &HashMap<String, u32>,
) -> Result<IndexMap<String, Vec<ParsedItem>>> {
    let html_text = std::fs::read_to_string(filepath)?;
    let document = Html::parse_document(&html_text);

    let card_sel = Selector::parse("div.bis__card").expect("invariant: valid selector");
    let item_sel = Selector::parse("div.item").expect("invariant: valid selector");
    let name_sel = Selector::parse("div.item__name").expect("invariant: valid selector");
    let inst_sel = Selector::parse("div.item__instance").expect("invariant: valid selector");
    let boss_sel = Selector::parse("div.item__boss").expect("invariant: valid selector");

    let mut results: IndexMap<String, Vec<ParsedItem>> = IndexMap::new();

    for card in document.select(&card_sel) {
        let Some(slot_id) = card.value().attr("id") else {
            continue;
        };
        let Some(slot) = map_slot(slot_id) else {
            continue;
        };

        let mut item_count = 0u32;
        for item_div in card.select(&item_sel) {
            // Get item name - need the direct .item__name div, not .item__name__wrapper
            let name: String = item_div
                .select(&name_sel)
                .filter(|el| {
                    let cls = el.value().attr("class").unwrap_or("");
                    cls.contains("item__name") && !cls.contains("item__name__wrapper")
                })
                .flat_map(|el| el.text())
                .collect::<String>()
                .trim()
                .to_string();

            if name.is_empty() {
                continue;
            }

            item_count += 1;
            let rank = if item_count == 1 {
                "BiS"
            } else if item_count <= 5 {
                "Optional"
            } else {
                continue; // Cap at 1 BiS + 4 Optional
            };

            let instance: String = item_div
                .select(&inst_sel)
                .flat_map(|el| el.text())
                .collect::<String>()
                .trim()
                .to_string();
            let boss: String = item_div
                .select(&boss_sel)
                .flat_map(|el| el.text())
                .collect::<String>()
                .trim()
                .to_string();

            let source = match (instance.is_empty(), boss.is_empty()) {
                (false, false) => format!("{instance} - {boss}"),
                (false, true) => instance,
                (true, false) => boss,
                (true, true) => String::new(),
            };

            // Resolve item ID
            let item_id = name_to_id
                .get(&name)
                .or_else(|| name_to_id.get(&name.to_lowercase()))
                .copied();

            results
                .entry(slot.to_string())
                .or_default()
                .push(ParsedItem {
                    rank: rank.to_string(),
                    name,
                    source,
                    item_id,
                });
        }
    }

    Ok(results)
}

pub fn run(spec: &str, output_override: Option<&str>) -> Result<()> {
    let root = common::project_root()?;
    let current_phase = common::load_current_phase(&root)?;
    let name_to_id = build_name_to_id(&root);

    let source_dir = root.join("sources").join("wowtbc").join(spec);
    let phase_files = find_phase_files(&source_dir, "html")?;

    if phase_files.is_empty() {
        anyhow::bail!("No phase-*.html files found in {}", source_dir.display());
    }

    let mut phases = IndexMap::new();
    for pf in &phase_files {
        let phase_name = pf.file_stem().unwrap().to_str().unwrap().to_string();
        println!("Parsing {}...", pf.file_name().unwrap().to_str().unwrap());
        let slots = parse_phase_file(pf, &name_to_id)?;
        phases.insert(phase_name, slots);
    }

    let output = ParsedOutput {
        current_phase,
        phases: phases.clone(),
    };

    let output_path = match output_override {
        Some(p) => std::path::PathBuf::from(p),
        None => root.join("output").join(spec).join("wtbc_bis_gear.json"),
    };
    write_output(&output, &output_path)?;

    println!(
        "\nWrote {} with {} phases.",
        output_path.display(),
        phases.len()
    );
    for (phase, slots) in &phases {
        let total_items: usize = slots.values().map(|v| v.len()).sum();
        let resolved: usize = slots
            .values()
            .flat_map(|v| v.iter())
            .filter(|i| i.item_id.is_some())
            .count();
        println!(
            "  {phase}: {} slots, {total_items} items ({resolved} with IDs)",
            slots.len()
        );
    }

    Ok(())
}
