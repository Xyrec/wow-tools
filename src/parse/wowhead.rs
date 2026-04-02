use indexmap::IndexMap;
use std::path::Path;

use anyhow::Result;
use regex::Regex;
use scraper::{Html, Selector};

use super::{ParsedItem, ParsedOutput, find_phase_files, write_output};
use crate::common;

/// Normalize wowhead h3 IDs to slot keys.
/// Matches Python: only normalizes 3 specific keys, passes through the rest.
fn normalize_slot(h3_id: &str) -> Option<String> {
    // Skip non-slot sections
    let skip = ["aldor-vs-scryer", "best-in-slot-gear", "changelog"];
    if skip.contains(&h3_id) {
        return None;
    }
    let skip_prefixes = ["best-in-slot", "other-", "crit-", "stamina-", "threat-"];
    if skip_prefixes.iter().any(|p| h3_id.starts_with(p)) {
        return None;
    }

    // Python only normalizes these 3 keys
    let normalized = match h3_id {
        "shoulder" => "shoulders",
        "shield" => "offhands",
        "libram" => "totems",
        other => other,
    };
    Some(normalized.to_string())
}

fn normalize_rank(raw: &str) -> Option<&'static str> {
    let r = raw.trim().to_lowercase();
    if r == "rank" || r.is_empty() {
        return None; // header row
    }
    if r == "bis" || r.starts_with("best") {
        Some("BiS")
    } else {
        Some("Optional")
    }
}

fn parse_phase_file(filepath: &Path) -> Result<IndexMap<String, Vec<ParsedItem>>> {
    let html_text = std::fs::read_to_string(filepath)?;
    let document = Html::parse_document(&html_text);

    let h3_sel = Selector::parse("h3").expect("invariant: valid selector");
    let table_sel = Selector::parse("table").expect("invariant: valid selector");
    let tr_sel = Selector::parse("tr").expect("invariant: valid selector");
    let td_sel = Selector::parse("td").expect("invariant: valid selector");
    let a_sel = Selector::parse("a").expect("invariant: valid selector");

    let item_id_re = Regex::new(r"/item=(\d+)").expect("invariant: valid regex");

    let mut results: IndexMap<String, Vec<ParsedItem>> = IndexMap::new();

    // Build a list of (h3_id, next_sibling_tables) by iterating all elements in order.
    // Strategy: find each h3 with an id, then find the next table sibling.
    // Since scraper gives us a DOM, we'll iterate h3 elements and find the table
    // that follows each h3.

    // Collect all h3 elements and their positions
    let body = document.root_element();

    // Get all elements in document order
    let h3_elements: Vec<_> = body.select(&h3_sel).collect();

    // For each h3, find the slot and then find the next table
    let mut current_slot: Option<String> = None;

    // We need to process elements in document order: h3 sets the slot, table provides items.
    // Use a different approach: iterate all children and track state.

    // Actually, let's use the node tree directly. Walk all nodes:
    for node in body.descendants() {
        if let Some(element) = node.value().as_element() {
            if element.name() == "h3" {
                if let Some(id) = element.attr("id") {
                    current_slot = normalize_slot(id);
                }
            }
        }
    }

    // Better approach: pair h3s with their following tables by using element references
    // Walk through pairs of (h3, next table)
    let all_h3: Vec<_> = h3_elements.iter().collect();
    let all_tables: Vec<_> = body.select(&table_sel).collect();

    // Build h3_id -> slot mapping, paired with following table
    // We'll use node IDs (which are document-order indices) to pair them
    let mut slot_tables: Vec<(String, scraper::ElementRef)> = Vec::new();

    for h3 in &all_h3 {
        let h3_id = h3.value().attr("id").unwrap_or("");
        if let Some(slot) = normalize_slot(h3_id) {
            let h3_node_id = h3.id();
            // Find the first table that comes after this h3 but before the next h3
            let next_h3_id = all_h3
                .iter()
                .find(|h| h.id() > h3_node_id && h.id() != h3_node_id)
                .map(|h| h.id());

            for table in &all_tables {
                let table_id = table.id();
                if table_id > h3_node_id {
                    if let Some(next_id) = next_h3_id {
                        if table_id < next_id {
                            slot_tables.push((slot, *table));
                            break;
                        }
                    } else {
                        slot_tables.push((slot, *table));
                        break;
                    }
                }
            }
        }
    }

    // Parse each slot table
    for (slot, table) in slot_tables {
        for row in table.select(&tr_sel) {
            let cells: Vec<_> = row.select(&td_sel).collect();
            if cells.is_empty() {
                continue;
            }

            // Check if header row (td with data-background="c7")
            if cells[0].value().attr("data-background") == Some("c7") {
                continue;
            }

            if cells.len() < 2 {
                continue;
            }

            let raw_rank = cells[0].text().collect::<String>();
            let rank = match normalize_rank(&raw_rank) {
                Some(r) => r,
                None => continue,
            };

            let item_name = cells[1].text().collect::<String>().trim().to_string();
            let source = if cells.len() > 2 {
                cells[2]
                    .text()
                    .collect::<String>()
                    .split_whitespace()
                    .collect::<Vec<_>>()
                    .join(" ")
            } else {
                String::new()
            };

            // Extract item ID from link (last match, matching Python behavior)
            let mut item_id = None;
            for a in cells[1].select(&a_sel) {
                if a.value().attr("data-entity") == Some("item") {
                    if let Some(href) = a.value().attr("href") {
                        if let Some(cap) = item_id_re.captures(href) {
                            item_id = cap[1].parse().ok();
                        }
                    }
                }
            }

            results
                .entry(slot.to_string())
                .or_default()
                .push(ParsedItem {
                    rank: rank.to_string(),
                    name: item_name,
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

    let source_dir = root.join("sources").join("wowhead").join(spec);
    let phase_files = find_phase_files(&source_dir, "html")?;

    if phase_files.is_empty() {
        anyhow::bail!("No phase-*.html files found in {}", source_dir.display());
    }

    let mut phases = IndexMap::new();
    for pf in &phase_files {
        let phase_name = pf.file_stem().unwrap().to_str().unwrap().to_string();
        println!("Parsing {}...", pf.file_name().unwrap().to_str().unwrap());
        let slots = parse_phase_file(pf)?;
        phases.insert(phase_name, slots);
    }

    let output = ParsedOutput {
        current_phase,
        phases: phases.clone(),
    };

    let output_path = match output_override {
        Some(p) => std::path::PathBuf::from(p),
        None => root.join("output").join(spec).join("wh_bis_gear.json"),
    };
    write_output(&output, &output_path)?;

    println!(
        "\nWrote {} with {} phases.",
        output_path.display(),
        phases.len()
    );
    for (phase, slots) in &phases {
        let total_items: usize = slots.values().map(|v| v.len()).sum();
        println!("  {phase}: {} slots, {total_items} items", slots.len());
    }

    Ok(())
}
