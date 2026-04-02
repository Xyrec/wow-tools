pub mod character;
pub mod specs;
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
    let spec = specs::find_spec(raw)?;
    Ok(spec.slug)
}

/// Return the default character data file for a resolved spec.
pub fn default_data_path(root: &Path, spec: &str) -> PathBuf {
    root.join("data").join(format!("{spec}.json"))
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
        assert_eq!(resolve_spec("resto-shaman").unwrap(), "resto-shaman");
        assert_eq!(resolve_spec("Resto-Shaman").unwrap(), "resto-shaman");
        assert_eq!(resolve_spec("ele-shaman").unwrap(), "elemental-shaman");
        assert_eq!(
            resolve_spec("elemental-shaman").unwrap(),
            "elemental-shaman"
        );
        assert_eq!(resolve_spec("prot-paladin").unwrap(), "prot-paladin");
        assert_eq!(resolve_spec("prot-warrior").unwrap(), "prot-warrior");
        assert_eq!(resolve_spec("fury-warrior").unwrap(), "fury-warrior");
        // Bare names without class suffix should fail
        assert!(resolve_spec("resto").is_err());
        assert!(resolve_spec("prot").is_err());
        assert!(resolve_spec("warrior").is_err());
    }

    #[test]
    fn test_wse_slot_order_length() {
        assert_eq!(WSE_SLOT_ORDER.len(), 17);
    }
}
