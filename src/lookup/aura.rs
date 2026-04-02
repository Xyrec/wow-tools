use std::collections::HashMap;
use std::path::Path;

use anyhow::{Context, Result};
use regex::Regex;

/// Parse `SpellAuraDefines.h` to extract `{aura_id: "Friendly Name"}`.
pub fn load_aura_names(path: &Path) -> Result<HashMap<u32, String>> {
    let text = std::fs::read_to_string(path)
        .with_context(|| format!("failed to read {}", path.display()))?;

    let enum_re = Regex::new(r"enum AuraType\s*\{([\s\S]*?)\}").expect("invariant: valid regex");
    let entry_re = Regex::new(r"(SPELL_AURA_\w+)\s*=\s*(\d+)").expect("invariant: valid regex");

    let mut result = HashMap::new();
    if let Some(m) = enum_re.find(&text) {
        for cap in entry_re.captures_iter(m.as_str()) {
            let name = &cap[1];
            let val: u32 = cap[2].parse().unwrap_or(0);
            let friendly = name
                .strip_prefix("SPELL_AURA_")
                .unwrap_or(name)
                .replace('_', " ")
                .split_whitespace()
                .map(|w| {
                    let mut chars = w.chars();
                    match chars.next() {
                        Some(c) => {
                            let upper: String = c.to_uppercase().collect();
                            format!("{upper}{}", chars.as_str().to_lowercase())
                        }
                        None => String::new(),
                    }
                })
                .collect::<Vec<_>>()
                .join(" ");
            result.insert(val, friendly);
        }
    }
    Ok(result)
}
