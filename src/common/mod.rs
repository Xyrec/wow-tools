pub mod character;
pub mod types;

use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};

// ---------------------------------------------------------------------------
// Project root discovery
// ---------------------------------------------------------------------------

/// Find the project root by looking for the `data/` directory.
/// Walks up from the executable's location, then falls back to cwd.
pub fn project_root() -> Result<PathBuf> {
    // Try relative to current exe
    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors().skip(1) {
            if ancestor.join("data").is_dir() {
                return Ok(ancestor.to_path_buf());
            }
        }
    }
    // Fall back to cwd
    let cwd = std::env::current_dir().context("failed to get current directory")?;
    for ancestor in cwd.ancestors() {
        if ancestor.join("data").is_dir() {
            return Ok(ancestor.to_path_buf());
        }
    }
    bail!("Could not find project root (no data/ directory found)")
}

// ---------------------------------------------------------------------------
// Spec resolution
// ---------------------------------------------------------------------------

pub fn resolve_spec(raw: &str) -> Result<&'static str> {
    match raw.trim().to_lowercase().as_str() {
        "resto" | "resto-shaman" => Ok("resto-shaman"),
        "ele" | "elemental" | "elemental-shaman" => Ok("elemental-shaman"),
        "prot" | "protection" | "prot-paladin" => Ok("prot-paladin"),
        other => bail!("Unknown spec '{}'. Use: resto, ele, prot.", other),
    }
}

/// Return the default character data file for a resolved spec.
pub fn default_data_path(root: &Path, spec: &str) -> PathBuf {
    let filename = match spec {
        "resto-shaman" => "resto.json",
        "elemental-shaman" => "elemental.json",
        "prot-paladin" => "prot-paladin.txt",
        _ => "resto.json",
    };
    root.join("data").join(filename)
}

// ---------------------------------------------------------------------------
// Phase helpers
// ---------------------------------------------------------------------------

/// Read `data/current-phase.txt` and return the phase string.
pub fn load_current_phase(root: &Path) -> Result<Option<String>> {
    let path = root.join("data").join("current-phase.txt");
    if !path.exists() {
        return Ok(None);
    }
    let content = std::fs::read_to_string(&path)
        .with_context(|| format!("failed to read {}", path.display()))?;
    Ok(Some(content.trim().to_string()))
}

// ---------------------------------------------------------------------------
// Database path
// ---------------------------------------------------------------------------

pub fn db_path(root: &Path) -> PathBuf {
    root.join("sources")
        .join("cmangos-tbc-db")
        .join("tbcmangos.sqlite")
}

// ---------------------------------------------------------------------------
// Slot ordering (WSE format)
// ---------------------------------------------------------------------------

pub const WSE_SLOT_ORDER: &[&str] = &[
    "Head",
    "Neck",
    "Shoulder",
    "Back",
    "Chest",
    "Wrist",
    "Hands",
    "Waist",
    "Legs",
    "Feet",
    "Finger 1",
    "Finger 2",
    "Trinket 1",
    "Trinket 2",
    "Main Hand",
    "Off Hand",
    "Ranged",
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resolve_spec() {
        assert_eq!(resolve_spec("resto").unwrap(), "resto-shaman");
        assert_eq!(resolve_spec("Resto").unwrap(), "resto-shaman");
        assert_eq!(resolve_spec("ele").unwrap(), "elemental-shaman");
        assert_eq!(
            resolve_spec("elemental-shaman").unwrap(),
            "elemental-shaman"
        );
        assert_eq!(resolve_spec("prot").unwrap(), "prot-paladin");
        assert!(resolve_spec("warrior").is_err());
    }

    #[test]
    fn test_wse_slot_order_length() {
        assert_eq!(WSE_SLOT_ORDER.len(), 17);
    }
}
