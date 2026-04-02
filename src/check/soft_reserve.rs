use std::collections::HashMap;
use std::path::Path;

use anyhow::{Result, bail};

/// Map RAID_KEYWORDS substrings to soft-reserve config tags.
const RAID_KEYWORD_TO_TAG: &[(&str, &str)] = &[
    ("karazhan", "karazhan"),
    ("gruul", "gruuls-lair"),
    ("magtheridon", "magtheridons-lair"),
    ("serpentshrine", "serpentshrine-cavern"),
    ("ssc", "serpentshrine-cavern"),
    ("tempest keep", "tempest-keep"),
    ("hyjal", "hyjal-summit"),
    ("black temple", "black-temple"),
    ("sunwell", "sunwell-plateau"),
    ("zul'aman", "zulaman"),
];

/// Pretty names for raid config tags.
pub const RAID_TAG_PRETTY_NAMES: &[(&str, &str)] = &[
    ("karazhan", "Karazhan"),
    ("gruuls-lair", "Gruul's Lair"),
    ("magtheridons-lair", "Magtheridon's Lair"),
    ("serpentshrine-cavern", "Serpentshrine Cavern"),
    ("tempest-keep", "Tempest Keep"),
    ("hyjal-summit", "Hyjal Summit"),
    ("black-temple", "Black Temple"),
    ("zulaman", "Zul'Aman"),
    ("sunwell-plateau", "Sunwell Plateau"),
];

pub fn raid_tag_pretty_name(tag: &str) -> &str {
    RAID_TAG_PRETTY_NAMES
        .iter()
        .find(|(t, _)| *t == tag)
        .map(|(_, n)| *n)
        .unwrap_or(tag)
}

/// Load soft-reserve config from data/soft-reserves.txt.
///
/// Returns (sr_counts, sr_groups):
///   sr_counts: raid-tag -> SR count (each tag in a group gets the count)
///   sr_groups: raid-tag -> group key (e.g. "gruuls-lair" -> "gruuls-lair+magtheridons-lair")
pub fn load_soft_reserves(
    path: Option<&Path>,
) -> Result<(HashMap<String, i32>, HashMap<String, String>)> {
    let path = match path {
        Some(p) => p.to_path_buf(),
        None => return Ok((HashMap::new(), HashMap::new())),
    };

    if !path.exists() {
        return Ok((HashMap::new(), HashMap::new()));
    }

    let content = std::fs::read_to_string(&path)?;
    let mut sr_counts: HashMap<String, i32> = HashMap::new();
    let mut sr_groups: HashMap<String, String> = HashMap::new();

    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, rest)) = line.split_once('=') else {
            continue;
        };
        let key = key.trim();
        // Strip inline comments
        let val_raw = rest.split('#').next().unwrap_or("").trim();
        let count: i32 = match val_raw.parse() {
            Ok(c) => c,
            Err(_) => {
                bail!(
                    "invalid value '{}' in soft-reserves.txt (expected integer) on line: {}",
                    val_raw,
                    line
                );
            }
        };
        if count < 0 {
            bail!(
                "negative SR count '{}' in soft-reserves.txt on line: {}",
                count,
                line
            );
        }

        let tags: Vec<&str> = key.split('+').map(|t| t.trim()).collect();
        for tag in &tags {
            if sr_counts.contains_key(*tag) {
                bail!(
                    "raid tag '{}' appears multiple times in soft-reserves.txt (check for duplicate or conflicting groups)",
                    tag
                );
            }
            sr_counts.insert(tag.to_string(), count);
            sr_groups.insert(tag.to_string(), key.to_string());
        }
    }

    Ok((sr_counts, sr_groups))
}

/// Map a source string to a soft-reserve config tag.
pub fn match_raid_tag(source: &str) -> Option<String> {
    let s = source.to_lowercase();
    for &(keyword, tag) in RAID_KEYWORD_TO_TAG {
        if s.contains(keyword) {
            return Some(tag.to_string());
        }
    }
    None
}
