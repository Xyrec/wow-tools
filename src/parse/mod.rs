pub mod atlasloot;
pub mod icy_veins;
pub mod wowhead;
pub mod wowtbc;

use indexmap::IndexMap;
use std::path::Path;

use anyhow::{Context, Result};

/// Shared item type for all parser outputs.
#[derive(Debug, Clone, serde::Serialize)]
pub struct ParsedItem {
    pub rank: String,
    pub name: String,
    pub source: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub item_id: Option<u32>,
}

/// Top-level structure written to JSON.
#[derive(Debug, serde::Serialize)]
pub struct ParsedOutput {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current_phase: Option<String>,
    pub phases: IndexMap<String, IndexMap<String, Vec<ParsedItem>>>,
}

/// Discover phase-*.html files in `source_dir`, sorted by name.
pub fn find_phase_files(source_dir: &Path, ext: &str) -> Result<Vec<std::path::PathBuf>> {
    let _pattern = format!("phase-*.{ext}");
    let mut files: Vec<_> = std::fs::read_dir(source_dir)
        .with_context(|| format!("failed to read {}", source_dir.display()))?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| {
            p.file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| n.starts_with("phase-") && n.ends_with(&format!(".{ext}")))
        })
        .collect();
    files.sort();
    Ok(files)
}

/// Write `ParsedOutput` as pretty-printed JSON.
pub fn write_output(output: &ParsedOutput, path: &Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let json = serde_json::to_string_pretty(output)?;
    std::fs::write(path, json)?;
    Ok(())
}
