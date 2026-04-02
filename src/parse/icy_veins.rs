use std::collections::HashMap;
use std::path::Path;

use indexmap::IndexMap;

use anyhow::Result;
use regex::Regex;
use scraper::{Html, Selector};

use super::{ParsedItem, ParsedOutput, find_phase_files, write_output};
use crate::common;

/// Map icy-veins slot names to canonical slot keys.
fn map_slot(name: &str) -> Option<&'static str> {
    Some(match name {
        "helm" => "head",
        "neck" => "neck",
        "shoulders" | "shoulder" => "shoulders",
        "back" | "cloak" => "back",
        "chest" => "chest",
        "wrists" | "bracer" | "bracers" => "wrists",
        "hands" | "gloves" => "hands",
        "belt" | "waist" => "waist",
        "legs" => "legs",
        "boots" | "feet" => "feet",
        "rings" | "ring 1" | "ring 2" => "rings",
        "trinkets" | "trinket 1" | "trinket 2" => "trinkets",
        "two-hand" | "one-hand" | "weapon" | "weapons" => "weapons",
        "off-hand" | "shield" | "shields" => "offhands",
        "relic" | "relics" | "libram" | "librams" => "totems",
        _ => return None,
    })
}

fn parse_phase_file(filepath: &Path) -> Result<IndexMap<String, Vec<ParsedItem>>> {
    let html_text = std::fs::read_to_string(filepath)?;
    let document = Html::parse_document(&html_text);

    let a_sel = Selector::parse("a").expect("invariant: valid selector");
    let item_re = Regex::new(r"item=(\d+)").expect("invariant: valid regex");
    let skip_classes = ["npc", "quest", "spell", "zone", "achievement"];

    let mut results: IndexMap<String, Vec<ParsedItem>> = IndexMap::new();

    // First pass: collect item names from all <a> tags
    let mut item_names: HashMap<u32, String> = HashMap::new();
    for a in document.select(&a_sel) {
        let wowhead = a.value().attr("data-wowhead").unwrap_or("");
        let css_class = a.value().attr("class").unwrap_or("");
        if wowhead.contains("item=") && !skip_classes.contains(&css_class) {
            if let Some(cap) = item_re.captures(wowhead) {
                let id: u32 = cap[1].parse().unwrap_or(0);
                if id != 0 {
                    item_names
                        .entry(id)
                        .or_insert_with(|| a.text().collect::<String>().trim().to_string());
                }
            }
        }
    }

    // Walk all descendants to track heading→table→row→item in document order.
    // Track: current rank (BiS/Optional from heading), current slot (from row).
    let mut current_rank = "BiS";
    let mut current_slot: Option<&'static str> = None;
    let _in_table = false;

    let _table_sel = Selector::parse("table").expect("invariant: valid selector");
    let tr_sel = Selector::parse("tr").expect("invariant: valid selector");
    let td_sel = Selector::parse("td").expect("invariant: valid selector");
    let strong_sel = Selector::parse("strong").expect("invariant: valid selector");
    let li_sel = Selector::parse("li").expect("invariant: valid selector");
    let _h2_sel = Selector::parse("h2").expect("invariant: valid selector");
    let _h3_sel = Selector::parse("h3").expect("invariant: valid selector");
    let _h4_sel = Selector::parse("h4").expect("invariant: valid selector");

    // Since scraper is DOM-based, collect all elements in document order
    // by iterating descendants and checking element types.

    // Strategy: Process each top-level element (heading or table) in order.
    // Use the tree structure: iterate all children of root/body.
    // Since HTML structure can be nested, we'll use a simpler approach:
    // collect all headings and tables, then walk them paired by document position.

    // Collect (node_index, type, element) tuples
    // node_index = position in descendants iterator
    enum DocElement<'a> {
        Heading(String),
        Table(scraper::ElementRef<'a>),
    }

    let root = document.root_element();
    let mut doc_elements: Vec<(usize, DocElement)> = Vec::new();

    for (idx, node) in root.descendants().enumerate() {
        if let Some(el) = node.value().as_element() {
            match el.name() {
                "h2" | "h3" | "h4" => {
                    let elem_ref = scraper::ElementRef::wrap(node).unwrap();
                    let text = elem_ref.text().collect::<String>().to_lowercase();
                    doc_elements.push((idx, DocElement::Heading(text)));
                }
                "table" => {
                    let elem_ref = scraper::ElementRef::wrap(node).unwrap();
                    doc_elements.push((idx, DocElement::Table(elem_ref)));
                }
                _ => {}
            }
        }
    }

    for (_idx, elem) in &doc_elements {
        match elem {
            DocElement::Heading(text) => {
                if text.contains("best in slot") {
                    current_rank = "BiS";
                } else if text.contains("other useful") {
                    current_rank = "Optional";
                }
            }
            DocElement::Table(table) => {
                for row in table.select(&tr_sel) {
                    let cells: Vec<_> = row.select(&td_sel).collect();
                    if cells.is_empty() {
                        continue;
                    }

                    // First cell: slot name
                    if let Some(first_cell) = cells.first() {
                        let slot_text = if let Some(strong) = first_cell.select(&strong_sel).next()
                        {
                            strong.text().collect::<String>().trim().to_lowercase()
                        } else {
                            first_cell.text().collect::<String>().trim().to_lowercase()
                        };

                        if let Some(slot) = map_slot(&slot_text) {
                            current_slot = Some(slot);
                        }
                    }

                    let Some(slot) = current_slot else {
                        continue;
                    };

                    if cells.len() < 2 {
                        continue;
                    }

                    let item_cell = &cells[1];
                    let lis: Vec<_> = item_cell.select(&li_sel).collect();

                    if !lis.is_empty() {
                        for li in lis {
                            let mut li_item_id: Option<u32> = None;
                            for a in li.select(&a_sel) {
                                let wowhead = a.value().attr("data-wowhead").unwrap_or("");
                                let css = a.value().attr("class").unwrap_or("");
                                if wowhead.contains("item=") && !skip_classes.contains(&css) {
                                    if let Some(cap) = item_re.captures(wowhead) {
                                        li_item_id = cap[1].parse().ok();
                                        break;
                                    }
                                }
                            }

                            if let Some(id) = li_item_id {
                                let source = li
                                    .text()
                                    .collect::<String>()
                                    .split_whitespace()
                                    .collect::<Vec<_>>()
                                    .join(" ");
                                let name = item_names.get(&id).cloned().unwrap_or_default();

                                results
                                    .entry(slot.to_string())
                                    .or_default()
                                    .push(ParsedItem {
                                        rank: current_rank.to_string(),
                                        name,
                                        source,
                                        item_id: Some(id),
                                    });
                            }
                        }
                    } else {
                        // Direct items in cell
                        for a in item_cell.select(&a_sel) {
                            let wowhead = a.value().attr("data-wowhead").unwrap_or("");
                            let css = a.value().attr("class").unwrap_or("");
                            if wowhead.contains("item=") && !skip_classes.contains(&css) {
                                if let Some(cap) = item_re.captures(wowhead) {
                                    let id: u32 = cap[1].parse().unwrap_or(0);
                                    if id != 0 {
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
                                        let name = item_names.get(&id).cloned().unwrap_or_default();

                                        results.entry(slot.to_string()).or_default().push(
                                            ParsedItem {
                                                rank: current_rank.to_string(),
                                                name,
                                                source,
                                                item_id: Some(id),
                                            },
                                        );
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Ok(results)
}

pub fn run(spec: &str, output_override: Option<&str>) -> Result<()> {
    let root = common::project_root()?;
    let current_phase = common::load_current_phase(&root)?;

    let source_dir = root.join("sources").join("icy-veins").join(spec);
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
        None => root.join("output").join(spec).join("iv_bis_gear.json"),
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
