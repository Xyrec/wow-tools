use super::ItemData;

/// Print a single item's stats (matches Python print_item exactly).
pub fn print_item(item: &ItemData) {
    println!(
        "  {}  (ilvl {} {})",
        item.name, item.item_level, item.quality
    );
    println!(
        "  ID: {}  |  Slot: {}  |  Type: {}",
        item.id,
        item.slot,
        item.item_type.as_deref().unwrap_or("-")
    );
    if item.armor != 0 {
        println!("  Armor: {}", item.armor);
    }
    if let Some(bv) = item.block_value {
        println!("  Block: {bv}");
    }
    if let Some(ref w) = item.weapon {
        for dmg in &w.damage {
            let school = if dmg.school != "Physical" {
                format!(" {}", dmg.school)
            } else {
                String::new()
            };
            println!("  {:.0} - {:.0}{} Damage", dmg.min, dmg.max, school);
        }
        println!("  Speed {:.2}  |  DPS {}", w.speed, format_dps(w.dps));
    }
    if !item.sockets.is_empty() {
        println!("  Sockets: {}", item.sockets.join(", "));
    }
    println!("  Stats:");
    for (stat, val) in &item.stats {
        println!("    {stat}: +{val}");
    }
    println!();
}

/// Print a side-by-side comparison table with diff column (matches Python print_compare).
pub fn print_compare(items: &[ItemData]) {
    // Build ordered list of all stats to show
    let mut all_stats: Vec<String> = vec!["Armor".to_string()];
    if items.iter().any(|i| i.block_value.is_some()) {
        all_stats.push("Block Value".to_string());
    }
    if items.iter().any(|i| i.weapon.is_some()) {
        all_stats.push("DPS".to_string());
        all_stats.push("Speed".to_string());
    }
    for item in items {
        for (s, _) in &item.stats {
            if !all_stats.contains(s) {
                all_stats.push(s.clone());
            }
        }
    }

    let names: Vec<&str> = items.iter().map(|i| i.name.as_str()).collect();
    let max_stat_w = all_stats.iter().map(|s| s.len()).max().unwrap_or(4);
    let col_w = names.iter().map(|n| n.len()).max().unwrap_or(8).max(8);

    // Header
    let mut header = format!("{:<width$}  ", "Stat", width = max_stat_w);
    for name in &names {
        header.push_str(&format!("{:>width$}  ", name, width = col_w));
    }
    if items.len() == 2 {
        header.push_str(&format!("{:>width$}", "Diff", width = col_w));
    }
    println!("{header}");
    println!("{}", "-".repeat(header.len()));

    // Subtitle row (ilvl / type)
    let mut sub = format!("{:<width$}  ", "(ilvl / type)", width = max_stat_w);
    for item in items {
        let label = format!(
            "{} {}",
            item.item_level,
            item.item_type.as_deref().unwrap_or("")
        );
        sub.push_str(&format!("{:>width$}  ", label, width = col_w));
    }
    println!("{sub}");
    println!("{}", "-".repeat(header.len()));

    // Stat rows
    for stat in &all_stats {
        let vals: Vec<f64> = items
            .iter()
            .map(|item| stat_value_for(item, stat))
            .collect();

        let is_float = stat == "DPS" || stat == "Speed";

        let mut row = format!("{:<width$}  ", stat, width = max_stat_w);
        for &v in &vals {
            let cell = format_cell(v, is_float, stat);
            row.push_str(&format!("{:>width$}  ", cell, width = col_w));
        }

        if items.len() == 2 {
            let diff = vals[0] - vals[1];
            let cell = format_diff(diff, is_float, stat);
            row.push_str(&format!("{:>width$}", cell, width = col_w));
        }

        println!("{row}");
    }
}

fn stat_value_for(item: &ItemData, stat: &str) -> f64 {
    match stat {
        "Armor" => item.armor as f64,
        "Block Value" => item.block_value.unwrap_or(0) as f64,
        "DPS" => item.weapon.as_ref().map_or(0.0, |w| w.dps),
        "Speed" => item.weapon.as_ref().map_or(0.0, |w| w.speed),
        _ => item.stat_value(stat) as f64,
    }
}

fn format_cell(v: f64, is_float: bool, stat: &str) -> String {
    if v == 0.0 {
        "-".to_string()
    } else if is_float {
        if stat == "DPS" {
            format_dps(v)
        } else {
            format!("{v:.2}")
        }
    } else {
        format!("+{}", v as i32)
    }
}

fn format_diff(diff: f64, is_float: bool, stat: &str) -> String {
    if diff == 0.0 {
        "-".to_string()
    } else if is_float {
        if stat == "DPS" {
            format!("{diff:+.1}")
        } else {
            format!("{diff:+.2}")
        }
    } else if diff > 0.0 {
        format!("+{}", diff as i32)
    } else {
        format!("{}", diff as i32)
    }
}

/// Format DPS value: Python uses round(dps, 1) then prints with no trailing zeros via default str().
/// Python `round(dps,1)` → `str()` gives e.g. "52.1" or "52.0" (always one decimal from round).
/// We match that with `{:.1}`.
fn format_dps(v: f64) -> String {
    format!("{v:.1}")
}
