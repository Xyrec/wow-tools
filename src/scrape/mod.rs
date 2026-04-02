use anyhow::{Context, Result};
use indexmap::IndexMap;

use crate::common;
use crate::common::specs;
use crate::parse::{ParsedItem, ParsedOutput, write_output};

// wowtbc phase key → our phase name
static PHASE_MAP: &[(&str, &str)] = &[
    ("pre-bis", "phase-0"),
    ("t4", "phase-1"),
    ("t5", "phase-2"),
    ("t6", "phase-3"),
    ("za", "phase-4"),
    ("swp", "phase-5"),
];

/// Map wowtbc slot names to our canonical slot keys.
fn map_slot(slot: &str) -> String {
    match slot {
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
        "finger 1" | "finger 2" => "rings",
        "trinket 1" | "trinket 2" => "trinkets",
        "weapon" => "weapons",
        "off hand" => "offhands",
        "relic" => "totems",
        other => other,
    }
    .to_string()
}

// ---------------------------------------------------------------------------
// Scraping and conversion
// ---------------------------------------------------------------------------

fn fetch_spec_data(wowtbc_slug: &str) -> Result<serde_json::Value> {
    let url = format!("https://wowtbc.gg/page-data/bis-list/{wowtbc_slug}/page-data.json");

    // Use ureq or fall back to shell curl
    let body = std::process::Command::new("curl")
        .args(["-sL", &url])
        .output()
        .context("failed to run curl")?;

    if !body.status.success() {
        anyhow::bail!("curl failed for {url}");
    }

    let data: serde_json::Value = serde_json::from_slice(&body.stdout)
        .with_context(|| format!("failed to parse JSON from {url}"))?;

    Ok(data)
}

fn format_source(item: &serde_json::Value) -> String {
    let source = item.get("source").and_then(|s| s.as_str()).unwrap_or("");
    let source_type = item
        .get("source_type")
        .and_then(|s| s.as_str())
        .unwrap_or("");
    let drop_chance = item.get("drop_chance").and_then(|d| d.as_f64());

    if source.is_empty() {
        return String::new();
    }

    let mut parts = vec![source.to_string()];
    if !source_type.is_empty() {
        parts.push(source_type.to_string());
    }
    if let Some(chance) = drop_chance {
        if chance > 0.0 {
            parts.push(format!("{:.0}%", chance * 100.0));
        }
    }
    parts.join(" — ")
}

fn convert_spec(data: &serde_json::Value) -> Result<ParsedOutput> {
    let bis_list = data
        .pointer("/result/pageContext/bisList")
        .and_then(|b| b.as_array())
        .context("missing bisList in page data")?;

    let current_phase = common::project_root()
        .ok()
        .and_then(|root| common::load_current_phase(&root).ok().flatten());

    // Build phases: for each phase key, collect items that appear in that phase
    let mut phases: IndexMap<String, IndexMap<String, Vec<ParsedItem>>> = IndexMap::new();

    for &(wtbc_key, our_phase) in PHASE_MAP {
        let mut slots: IndexMap<String, Vec<ParsedItem>> = IndexMap::new();

        // Collect all items that appear in this phase, sorted by value descending
        let mut phase_items: Vec<&serde_json::Value> = bis_list
            .iter()
            .filter(|item| {
                // Item appears in this phase if the phase key exists and has any content
                // beyond just {enchant: {recipe: false}}
                let phase_data = item.get(wtbc_key);
                if phase_data.is_none() {
                    return false;
                }
                // Item is relevant to this phase if it's BiS or listed in the phase array
                let is_bis = phase_data
                    .and_then(|p| p.get("bis"))
                    .and_then(|b| b.as_bool())
                    .unwrap_or(false);
                let in_phase_list = item
                    .get("phase")
                    .and_then(|p| p.as_array())
                    .map(|arr| {
                        arr.iter().any(|v| {
                            let phase_name = v.as_str().unwrap_or("");
                            match wtbc_key {
                                "pre-bis" => phase_name == "Pre-Bis",
                                "t4" => phase_name == "T4",
                                "t5" => phase_name == "T5",
                                "t6" => phase_name == "T6",
                                "za" => phase_name == "ZA",
                                "swp" => phase_name == "SWP",
                                _ => false,
                            }
                        })
                    })
                    .unwrap_or(false);
                is_bis || in_phase_list
            })
            .collect();

        // Sort by value descending (highest value = best item)
        phase_items.sort_by(|a, b| {
            let va = b.get("value").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let vb = a.get("value").and_then(|v| v.as_f64()).unwrap_or(0.0);
            va.partial_cmp(&vb).unwrap_or(std::cmp::Ordering::Equal)
        });

        for item in phase_items {
            let name = item.get("name").and_then(|n| n.as_str()).unwrap_or("");
            let slot_raw = item.get("slot").and_then(|s| s.as_str()).unwrap_or("");
            let slot = map_slot(slot_raw);
            let is_bis = item
                .get(wtbc_key)
                .and_then(|p| p.get("bis"))
                .and_then(|b| b.as_bool())
                .unwrap_or(false);

            let rank = if is_bis { "BiS" } else { "Optional" };
            let source = format_source(item);

            slots.entry(slot).or_default().push(ParsedItem {
                rank: rank.to_string(),
                name: name.to_string(),
                source,
                item_id: None, // wowtbc doesn't provide item IDs in the JSON
            });
        }

        // Cap at 1 BiS + 4 Optional per slot
        for items in slots.values_mut() {
            let mut bis_count = 0u32;
            let mut opt_count = 0u32;
            items.retain(|item| {
                if item.rank == "BiS" {
                    bis_count += 1;
                    bis_count <= 1
                } else {
                    opt_count += 1;
                    opt_count <= 4
                }
            });
        }

        if !slots.is_empty() {
            phases.insert(our_phase.to_string(), slots);
        }
    }

    Ok(ParsedOutput {
        current_phase,
        phases,
    })
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

pub fn run(spec: Option<&str>) -> Result<()> {
    let root = common::project_root()?;

    let all = specs::all_specs();
    let specs_to_scrape: Vec<&specs::SpecInfo> = if let Some(filter) = spec {
        let f = filter.to_lowercase();
        all.iter()
            .filter(|s| s.slug.contains(&f) || s.wowtbc_slug.contains(&f))
            .collect()
    } else {
        all.iter().collect()
    };

    if specs_to_scrape.is_empty() {
        anyhow::bail!("No matching specs found for '{}'", spec.unwrap_or(""));
    }

    println!(
        "Scraping {} spec(s) from wowtbc.gg...\n",
        specs_to_scrape.len()
    );

    for spec in &specs_to_scrape {
        print!("  {:<25} ", spec.slug);

        match fetch_spec_data(spec.wowtbc_slug) {
            Ok(data) => {
                let output = convert_spec(&data)?;
                let output_dir = root.join("output").join(spec.slug);
                let output_path = output_dir.join("wtbc_bis_gear.json");
                write_output(&output, &output_path)?;

                let total_items: usize = output
                    .phases
                    .values()
                    .flat_map(|slots| slots.values())
                    .map(|items| items.len())
                    .sum();
                println!(
                    "✓ {} phases, {} items -> {}",
                    output.phases.len(),
                    total_items,
                    output_path.display()
                );
            }
            Err(e) => {
                println!("✗ {e}");
            }
        }
    }

    println!("\nDone.");
    Ok(())
}
