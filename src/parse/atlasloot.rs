use std::collections::{HashMap, HashSet};

use indexmap::IndexMap;
use std::path::Path;

use anyhow::{Context, Result};
use regex::Regex;
use rusqlite::Connection;

use super::{ParsedItem, ParsedOutput, write_output};
use crate::common;

/// Map our spec slugs to AtlasLoot data keys per phase file.
/// Keys vary across phases (e.g. "ShamanResto" in P0, "ShamanRestoration" in P1).
/// Some specs share a key in certain phases (e.g. Rogue has one entry in P0/P1).
static SPEC_LUA_KEYS: &[(&str, &[(&str, &str)])] = &[
    // Shaman
    (
        "resto-shaman",
        &[
            ("prebisDB.lua", "ShamanResto"),
            ("phaseoneDB.lua", "ShamanRestoration"),
            ("phasetwoDB.lua", "ShamanRestoration_P2"),
        ],
    ),
    (
        "elemental-shaman",
        &[
            ("prebisDB.lua", "ShamanEle"),
            ("phaseoneDB.lua", "ShamanElemental"),
            ("phasetwoDB.lua", "ShamanElemental_P2"),
        ],
    ),
    (
        "enhancement-shaman",
        &[
            ("prebisDB.lua", "ShamanEnh"),
            ("phaseoneDB.lua", "ShamanEnhancement"),
            ("phasetwoDB.lua", "ShamanEnhancement_P2"),
        ],
    ),
    // Paladin
    (
        "holy-paladin",
        &[
            ("prebisDB.lua", "PalHoly"),
            ("phaseoneDB.lua", "PaladinHoly_P1"),
            ("phasetwoDB.lua", "PaladinHoly_P2"),
        ],
    ),
    (
        "prot-paladin",
        &[
            ("prebisDB.lua", "PalProt"),
            ("phaseoneDB.lua", "PaladinProtection_P1"),
            ("phasetwoDB.lua", "PaladinProtection_P2"),
        ],
    ),
    (
        "ret-paladin",
        &[
            ("prebisDB.lua", "PalRet"),
            ("phaseoneDB.lua", "PaladinRetribution"),
            ("phasetwoDB.lua", "PaladinRetribution_P2"),
        ],
    ),
    // Priest
    (
        "holy-priest",
        &[
            ("prebisDB.lua", "PriestHoly"),
            ("phaseoneDB.lua", "PriestHoly"),
            ("phasetwoDB.lua", "PriestHoly_P2"),
        ],
    ),
    (
        "shadow-priest",
        &[
            ("prebisDB.lua", "PriestShadow"),
            ("phaseoneDB.lua", "PriestShadow"),
            ("phasetwoDB.lua", "PriestShadow_P2"),
        ],
    ),
    // Druid
    (
        "balance-druid",
        &[
            ("prebisDB.lua", "DruidBalance"),
            ("phaseoneDB.lua", "DruidBalance_P1"),
            ("phasetwoDB.lua", "DruidBalance_P2"),
        ],
    ),
    (
        "feral-tank-druid",
        &[
            ("prebisDB.lua", "DruidBear"),
            ("phaseoneDB.lua", "DruidBear_P1"),
            ("phasetwoDB.lua", "DruidBear_P2"),
        ],
    ),
    (
        "feral-dps-druid",
        &[
            ("prebisDB.lua", "DruidCat"),
            ("phaseoneDB.lua", "DruidCat_P1"),
            ("phasetwoDB.lua", "DruidCat_P2"),
        ],
    ),
    (
        "resto-druid",
        &[
            ("prebisDB.lua", "DruidResto"),
            ("phaseoneDB.lua", "DruidRestoration_P1"),
            ("phasetwoDB.lua", "DruidRestoration_P2"),
        ],
    ),
    // Warrior
    (
        "arms-warrior",
        &[
            ("prebisDB.lua", "WarriorArms"),
            ("phaseoneDB.lua", "WarriorArms"),
            ("phasetwoDB.lua", "WarriorArms_P2"),
        ],
    ),
    (
        "fury-warrior",
        &[
            ("prebisDB.lua", "WarriorFury"),
            ("phaseoneDB.lua", "WarriorFury"),
            ("phasetwoDB.lua", "WarriorFury_P2"),
        ],
    ),
    (
        "prot-warrior",
        &[
            ("prebisDB.lua", "WarriorProtection"),
            ("phaseoneDB.lua", "WarriorProt"),
            ("phasetwoDB.lua", "WarriorProt_P2"),
        ],
    ),
    // Hunter
    (
        "bm-hunter",
        &[
            ("prebisDB.lua", "HunterBM"),
            ("phaseoneDB.lua", "HunterBM_P1"),
            ("phasetwoDB.lua", "HunterBM_P2"),
        ],
    ),
    (
        "marks-hunter",
        &[
            ("prebisDB.lua", "HunterMM"),
            ("phaseoneDB.lua", "HunterMM_P1"),
            ("phasetwoDB.lua", "HunterMM_P2"),
        ],
    ),
    (
        "survival-hunter",
        &[
            ("prebisDB.lua", "HunterSV"),
            ("phaseoneDB.lua", "HunterSurv_P1"),
            ("phasetwoDB.lua", "HunterSurv_P2"),
        ],
    ),
    // Rogue (single entry in P0/P1, per-spec in P2)
    (
        "assassination-rogue",
        &[
            ("prebisDB.lua", "Rogue"),
            ("phaseoneDB.lua", "Rogue"),
            ("phasetwoDB.lua", "Rogue_P2"),
        ],
    ),
    (
        "combat-rogue",
        &[
            ("prebisDB.lua", "Rogue"),
            ("phaseoneDB.lua", "Rogue"),
            ("phasetwoDB.lua", "Rogue_P2"),
        ],
    ),
    (
        "subtlety-rogue",
        &[
            ("prebisDB.lua", "Rogue"),
            ("phaseoneDB.lua", "Rogue"),
            ("phasetwoDB.lua", "Rogue_P2"),
        ],
    ),
    // Mage
    (
        "arcane-mage",
        &[
            ("prebisDB.lua", "MageArc"),
            ("phaseoneDB.lua", "MageArcane_P1"),
            ("phasetwoDB.lua", "MageArcane_P2"),
        ],
    ),
    (
        "fire-mage",
        &[
            ("prebisDB.lua", "Mage Fire"),
            ("phaseoneDB.lua", "MageFire_P1"),
            ("phasetwoDB.lua", "MageFire_P2"),
        ],
    ),
    (
        "frost-mage",
        &[
            ("prebisDB.lua", "MageFrost"),
            ("phaseoneDB.lua", "MageFrost_P1"),
            ("phasetwoDB.lua", "MageFrost_P2"),
        ],
    ),
    // Warlock (Demonology missing from P1)
    (
        "affliction-warlock",
        &[
            ("prebisDB.lua", "WarlockAff"),
            ("phaseoneDB.lua", "WarlockAffliction"),
            ("phasetwoDB.lua", "WarlockAffliction_P2"),
        ],
    ),
    (
        "demo-warlock",
        &[
            ("prebisDB.lua", "WarlockDemonology"),
            ("phasetwoDB.lua", "WarlockDemonology_P2"),
        ],
    ),
    (
        "destro-warlock",
        &[
            ("prebisDB.lua", "WarlockDestruction"),
            ("phaseoneDB.lua", "WarlockDestruction"),
            ("phasetwoDB.lua", "WarlockDestruction_P2"),
        ],
    ),
];

static PHASE_MAP: &[(&str, &str)] = &[
    ("prebisDB.lua", "phase-0"),
    ("phaseoneDB.lua", "phase-1"),
    ("phasetwoDB.lua", "phase-2"),
];

static SLOT_MAP: &[(&str, &str)] = &[
    ("Head", "head"),
    ("Shoulders", "shoulders"),
    ("Back", "back"),
    ("Chest", "chest"),
    ("Wrist", "wrists"),
    ("Hands", "hands"),
    ("Waist", "waist"),
    ("Legs", "legs"),
    ("Feet", "feet"),
    ("Neck", "neck"),
    ("Rings", "rings"),
    ("Trinkets", "trinkets"),
    ("Main Hand", "weapons"),
    ("Onehand", "weapons"),
    ("Off Hand", "offhands"),
    ("Offhand", "offhands"),
    ("Shield", "offhands"),
    ("Twohand", "weapons"),
    ("Ranged", "totems"),
    ("Wand", "totems"),
    ("Totems", "totems"),
];

static INSTANCE_NAMES: &[(u32, &str)] = &[
    (269, "Black Morass"),
    (532, "Karazhan"),
    (534, "Hyjal Summit"),
    (540, "Shattered Halls"),
    (542, "Blood Furnace"),
    (543, "Hellfire Ramparts"),
    (544, "Magtheridon's Lair"),
    (545, "Steamvault"),
    (546, "Underbog"),
    (547, "Slave Pens"),
    (548, "Serpentshrine Cavern"),
    (550, "Tempest Keep"),
    (552, "Arcatraz"),
    (553, "Botanica"),
    (554, "Mechanar"),
    (555, "Shadow Labyrinth"),
    (556, "Sethekk Halls"),
    (557, "Mana-Tombs"),
    (558, "Auchenai Crypts"),
    (560, "Old Hillsbrad Foothills"),
    (564, "Black Temple"),
    (565, "Gruul's Lair"),
    (568, "Zul'Aman"),
    (580, "Sunwell Plateau"),
    (585, "Magisters' Terrace"),
];

static REP_RANKS: &[(u32, &str)] = &[
    (4, "Friendly"),
    (5, "Honored"),
    (6, "Revered"),
    (7, "Exalted"),
];

static BADGE_VENDORS: &[u32] = &[18525, 25046, 27666];

static PVP_VENDOR_KEYWORDS: &[&str] = &[
    "arena",
    "gladiator",
    "pvp",
    "honor",
    "conquest",
    "battleground",
];

/// Tier token vendor → {InventoryType: (boss_name, instance_name)}
struct TierTokenSource {
    vendor_name: &'static str,
    slots: &'static [(u32, &'static str, &'static str)], // (inv_type, boss, instance)
}

static TIER_TOKEN_SOURCES: &[TierTokenSource] = &[
    TierTokenSource {
        vendor_name: "arodis sunblade",
        slots: &[
            (1, "Prince Malchezaar", "Karazhan"),
            (3, "High King Maulgar", "Gruul's Lair"),
            (5, "Magtheridon", "Magtheridon's Lair"),
            (7, "Gruul the Dragonkiller", "Gruul's Lair"),
            (10, "The Curator", "Karazhan"),
            (20, "Magtheridon", "Magtheridon's Lair"),
        ],
    },
    TierTokenSource {
        vendor_name: "veynna dawnstar",
        slots: &[
            (1, "Lady Vashj", "Serpentshrine Cavern"),
            (3, "Void Reaver", "Tempest Keep"),
            (5, "Kael'thas Sunstrider", "Tempest Keep"),
            (7, "Fathom-Lord Karathress", "Serpentshrine Cavern"),
            (10, "Leotheras the Blind", "Serpentshrine Cavern"),
            (20, "Kael'thas Sunstrider", "Tempest Keep"),
        ],
    },
    TierTokenSource {
        vendor_name: "tydormu",
        slots: &[
            (1, "Archimonde", "Hyjal Summit"),
            (3, "Mother Shahraz", "Black Temple"),
            (5, "Illidan Stormrage", "Black Temple"),
            (7, "The Illidari Council", "Black Temple"),
            (10, "Azgalor", "Hyjal Summit"),
            (20, "Illidan Stormrage", "Black Temple"),
        ],
    },
    TierTokenSource {
        vendor_name: "theremis",
        slots: &[
            (6, "Eredar Twins", "Sunwell Plateau"),
            (8, "Eredar Twins", "Sunwell Plateau"),
            (9, "Eredar Twins", "Sunwell Plateau"),
        ],
    },
];

fn instance_name(map_id: u32) -> Option<&'static str> {
    INSTANCE_NAMES
        .iter()
        .find(|(id, _)| *id == map_id)
        .map(|(_, name)| *name)
}

fn rep_rank_name(rank_id: u32) -> &'static str {
    REP_RANKS
        .iter()
        .find(|(id, _)| *id == rank_id)
        .map(|(_, name)| *name)
        .unwrap_or("Unknown")
}

fn tier_token_source(vendor_name: &str, inv_type: u32) -> Option<(&'static str, &'static str)> {
    for src in TIER_TOKEN_SOURCES {
        if src.vendor_name == vendor_name {
            for &(it, boss, inst) in src.slots {
                if it == inv_type {
                    return Some((boss, inst));
                }
            }
        }
    }
    None
}

// ---------------------------------------------------------------------------
// AtlasLoot dungeon/raid data parsing
// ---------------------------------------------------------------------------

fn build_dungeon_item_lookup(root: &Path) -> HashMap<u32, String> {
    let lua_path = root
        .join("sources")
        .join("atlasloot")
        .join("AtlasLootClassic_DungeonsAndRaids")
        .join("data-tbc.lua");

    let Ok(text) = std::fs::read_to_string(&lua_path) else {
        return HashMap::new();
    };

    let instance_re = Regex::new(r#"data\["([^"]+)"\]\s*=\s*\{"#).expect("invariant: valid regex");
    let boss_re = Regex::new(
        r#"name\s*=\s*(?:AL\["([^"]+)"\]|format\([^,]+,\s*AL\["([^"]+)"\]\)|"([^"]+)")"#,
    )
    .expect("invariant: valid regex");
    let iid_re = Regex::new(r"InstanceID\s*=\s*(\d+)").expect("invariant: valid regex");
    let item_re = Regex::new(r"\{\s*\d+\s*,\s*(\d+)\s*\}").expect("invariant: valid regex");
    let normal_tag = Regex::new(r"\[NORMAL_DIFF\]\s*=\s*\{").expect("invariant: valid regex");
    let heroic_tag = Regex::new(r"\[HEROIC_DIFF\]\s*=\s*\{").expect("invariant: valid regex");

    let trash_indicators = ["trash", "zone drop", "boe", "random"];
    let mut result: HashMap<u32, String> = HashMap::new();

    // Split text into instance blocks by finding each data["..."] = { pattern
    let inst_matches: Vec<_> = instance_re.captures_iter(&text).collect();
    for (idx, inst_match) in inst_matches.iter().enumerate() {
        let inst_key = &inst_match[1];
        let block_start = inst_match.get(0).unwrap().end();
        let block_end = if idx + 1 < inst_matches.len() {
            inst_matches[idx + 1].get(0).unwrap().start()
        } else {
            text.len()
        };
        let inst_block = &text[block_start..block_end];

        let map_id = iid_re
            .captures(inst_block)
            .and_then(|c| c[1].parse::<u32>().ok());
        let inst_name = map_id.and_then(instance_name).unwrap_or(inst_key);

        let is_world_boss = inst_key.contains("WorldBoss");
        let items_start = inst_block.find("items");
        let is_raid = items_start.map_or(false, |pos| inst_block[..pos].contains("RAID"));

        let max_players: u32 = if is_world_boss {
            0
        } else if is_raid {
            25
        } else {
            5
        };

        let boss_matches: Vec<_> = boss_re.captures_iter(inst_block).collect();

        for (i, boss_match) in boss_matches.iter().enumerate() {
            let boss_name = boss_match
                .get(1)
                .or(boss_match.get(2))
                .or(boss_match.get(3))
                .map(|m| m.as_str())
                .unwrap_or("");
            if boss_name.is_empty() {
                continue;
            }

            let start = boss_match.get(0).unwrap().end();
            let end = if i + 1 < boss_matches.len() {
                boss_matches[i + 1].get(0).unwrap().start()
            } else {
                inst_block.len()
            };
            let boss_block = &inst_block[start..end];

            let mut normal_ids: HashSet<u32> = HashSet::new();
            let mut heroic_ids: HashSet<u32> = HashSet::new();

            // Extract items from NORMAL_DIFF section
            if let Some(m) = normal_tag.find(boss_block) {
                let content_start = m.end();
                // Content extends to next [*_DIFF] or end of boss_block
                let content_end = boss_block[content_start..]
                    .find("[HEROIC_DIFF]")
                    .or_else(|| boss_block[content_start..].find("[NORMAL_DIFF]"))
                    .map(|p| content_start + p)
                    .unwrap_or(boss_block.len());
                for m in item_re.captures_iter(&boss_block[content_start..content_end]) {
                    if let Ok(id) = m[1].parse() {
                        normal_ids.insert(id);
                    }
                }
            }
            // Extract items from HEROIC_DIFF section
            if let Some(m) = heroic_tag.find(boss_block) {
                let content_start = m.end();
                let content_end = boss_block[content_start..]
                    .find("[NORMAL_DIFF]")
                    .or_else(|| boss_block[content_start..].find("[HEROIC_DIFF]"))
                    .map(|p| content_start + p)
                    .unwrap_or(boss_block.len());
                for m in item_re.captures_iter(&boss_block[content_start..content_end]) {
                    if let Ok(id) = m[1].parse() {
                        heroic_ids.insert(id);
                    }
                }
            }

            let heroic_only: HashSet<u32> = heroic_ids.difference(&normal_ids).copied().collect();
            let all_ids: HashSet<u32> = normal_ids.union(&heroic_ids).copied().collect();

            for item_id in all_ids {
                if let Some(existing) = result.get(&item_id) {
                    let existing_is_trash = trash_indicators
                        .iter()
                        .any(|t| existing.to_lowercase().contains(t));
                    if !existing_is_trash {
                        continue;
                    }
                }

                let heroic_tag = if heroic_only.contains(&item_id) {
                    " (H)"
                } else {
                    ""
                };

                let source = if is_world_boss {
                    format!("World Boss: {boss_name}")
                } else if max_players <= 5 {
                    format!("Drop: {boss_name}{heroic_tag} ({inst_name})")
                } else {
                    format!("Drop: {boss_name} - {inst_name}")
                };

                result.insert(item_id, source);
            }
        }
    }

    result
}

// ---------------------------------------------------------------------------
// DB-based source classification
// ---------------------------------------------------------------------------

fn load_item_info(conn: &Connection, item_ids: &HashSet<u32>) -> HashMap<u32, (String, u32)> {
    if item_ids.is_empty() {
        return HashMap::new();
    }
    let placeholders: String = item_ids.iter().map(|_| "?").collect::<Vec<_>>().join(",");
    let sql = format!(
        "SELECT entry, name, InventoryType FROM item_template WHERE entry IN ({placeholders})"
    );
    let mut stmt = conn.prepare(&sql).unwrap();
    let params: Vec<_> = item_ids.iter().map(|id| *id as i64).collect();
    let param_refs: Vec<&dyn rusqlite::types::ToSql> = params
        .iter()
        .map(|p| p as &dyn rusqlite::types::ToSql)
        .collect();
    let rows = stmt
        .query_map(param_refs.as_slice(), |row| {
            Ok((
                row.get::<_, u32>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, u32>(2)?,
            ))
        })
        .unwrap();
    rows.filter_map(|r| r.ok())
        .map(|(id, name, inv)| (id, (name, inv)))
        .collect()
}

fn classify_item_sources(
    conn: &Connection,
    item_ids: &HashSet<u32>,
    root: &Path,
) -> HashMap<u32, String> {
    if item_ids.is_empty() {
        return HashMap::new();
    }

    let mut sources: HashMap<u32, String> = HashMap::new();
    let mut remaining: HashSet<u32> = item_ids.clone();

    // Step 0: AtlasLoot dungeon data
    let al_lookup = build_dungeon_item_lookup(root);
    for &item_id in &*item_ids {
        if let Some(source) = al_lookup.get(&item_id) {
            sources.insert(item_id, source.clone());
            remaining.remove(&item_id);
        }
    }

    // Build encounter name -> map lookup
    let mut encounter_maps: HashMap<String, u32> = HashMap::new();
    if let Ok(mut stmt) =
        conn.prepare("SELECT MapId, EncounterName FROM instance_dungeon_encounters")
    {
        if let Ok(rows) = stmt.query_map([], |row| {
            Ok((row.get::<_, u32>(0)?, row.get::<_, String>(1)?))
        }) {
            for row in rows.flatten() {
                encounter_maps.insert(row.1.to_lowercase().trim().to_string(), row.0);
            }
        }
    }

    // Helper: resolve creature to instance
    let get_creature_instance =
        |conn: &Connection, creature_id: u32| -> Option<(String, &'static str, u32)> {
            let name: String = conn
                .query_row(
                    "SELECT name FROM creature_template WHERE entry=?",
                    [creature_id],
                    |row| row.get(0),
                )
                .ok()?;
            let creature_name = name.strip_suffix(" (1)").unwrap_or(&name).to_string();

            // Try direct spawn
            let mut map_id: Option<u32> = conn
                .query_row(
                    "SELECT map FROM creature WHERE id=? LIMIT 1",
                    [creature_id],
                    |row| row.get(0),
                )
                .ok();

            // Try base creature (heroic variant)
            if map_id.is_none() {
                if let Ok(base_id) = conn.query_row(
                    "SELECT entry FROM creature_template WHERE HeroicEntry=?",
                    [creature_id],
                    |row| row.get::<_, u32>(0),
                ) {
                    map_id = conn
                        .query_row(
                            "SELECT map FROM creature WHERE id=? LIMIT 1",
                            [base_id],
                            |row| row.get(0),
                        )
                        .ok();
                }
            }

            // Try encounter name match
            if map_id.is_none() {
                map_id = encounter_maps.get(&creature_name.to_lowercase()).copied();
            }

            let map_id = map_id?;
            let inst = instance_name(map_id)?;
            let max_players: u32 = conn
                .query_row(
                    "SELECT maxPlayers FROM instance_template WHERE map=?",
                    [map_id],
                    |row| row.get(0),
                )
                .ok()?;

            Some((creature_name, inst, max_players))
        };

    // Step 1: Creature drops
    if !remaining.is_empty() {
        let placeholders: String = remaining.iter().map(|_| "?").collect::<Vec<_>>().join(",");
        let params: Vec<i64> = remaining.iter().map(|&id| id as i64).collect();
        let param_refs: Vec<&dyn rusqlite::types::ToSql> = params
            .iter()
            .map(|p| p as &dyn rusqlite::types::ToSql)
            .collect();

        // Reference loot
        let mut ref_map: HashMap<u32, Vec<u32>> = HashMap::new();
        {
            let sql = format!(
                "SELECT item, entry FROM reference_loot_template WHERE item IN ({placeholders})"
            );
            if let Ok(mut stmt) = conn.prepare(&sql) {
                if let Ok(rows) = stmt.query_map(param_refs.as_slice(), |row| {
                    Ok((row.get::<_, u32>(0)?, row.get::<_, u32>(1)?))
                }) {
                    for row in rows.flatten() {
                        ref_map.entry(row.0).or_default().push(row.1);
                    }
                }
            }
        }

        let all_ref_entries: HashSet<u32> = ref_map.values().flatten().copied().collect();
        let mut ref_to_creatures: HashMap<u32, Vec<u32>> = HashMap::new();
        if !all_ref_entries.is_empty() {
            let neg_refs: Vec<i64> = all_ref_entries.iter().map(|&r| -(r as i64)).collect();
            let neg_ph: String = neg_refs.iter().map(|_| "?").collect::<Vec<_>>().join(",");
            let neg_refs_sql: Vec<&dyn rusqlite::types::ToSql> = neg_refs
                .iter()
                .map(|p| p as &dyn rusqlite::types::ToSql)
                .collect();
            let sql = format!(
                "SELECT mincountOrRef, entry FROM creature_loot_template WHERE mincountOrRef IN ({neg_ph})"
            );
            if let Ok(mut stmt) = conn.prepare(&sql) {
                if let Ok(rows) = stmt.query_map(neg_refs_sql.as_slice(), |row| {
                    Ok((row.get::<_, i64>(0)?, row.get::<_, u32>(1)?))
                }) {
                    for row in rows.flatten() {
                        ref_to_creatures
                            .entry((-row.0) as u32)
                            .or_default()
                            .push(row.1);
                    }
                }
            }
        }

        // Direct creature loot
        let mut direct_drops: HashMap<u32, Vec<u32>> = HashMap::new();
        {
            let sql = format!(
                "SELECT item, entry FROM creature_loot_template WHERE item IN ({placeholders})"
            );
            if let Ok(mut stmt) = conn.prepare(&sql) {
                if let Ok(rows) = stmt.query_map(param_refs.as_slice(), |row| {
                    Ok((row.get::<_, u32>(0)?, row.get::<_, u32>(1)?))
                }) {
                    for row in rows.flatten() {
                        direct_drops.entry(row.0).or_default().push(row.1);
                    }
                }
            }
        }

        let generic_names = ["trash", "zone drop", "trash mobs"];
        for item_id in remaining.clone() {
            let mut creatures: HashSet<u32> = HashSet::new();
            for ref_entry in ref_map.get(&item_id).unwrap_or(&vec![]) {
                for &cid in ref_to_creatures.get(ref_entry).unwrap_or(&vec![]) {
                    creatures.insert(cid);
                }
            }
            for &cid in direct_drops.get(&item_id).unwrap_or(&vec![]) {
                creatures.insert(cid);
            }

            let mut best: Option<(String, &str, u32)> = None;
            for cid in &creatures {
                if let Some(info) = get_creature_instance(conn, *cid) {
                    if let Some(ref b) = best {
                        let best_generic = generic_names.contains(&b.0.to_lowercase().as_str());
                        let new_generic = generic_names.contains(&info.0.to_lowercase().as_str());
                        if (best_generic && !new_generic)
                            || (!best_generic && !new_generic && info.2 < b.2)
                        {
                            best = Some(info);
                        }
                    } else {
                        best = Some(info);
                    }
                }
            }

            if let Some((creature_name, inst, max_players)) = best {
                let source = if max_players <= 5 {
                    format!("Drop: {creature_name} ({inst})")
                } else {
                    format!("Drop: {creature_name} - {inst}")
                };
                sources.insert(item_id, source);
                remaining.remove(&item_id);
            }
        }
    }

    // Step 2: Reputation vendor items
    if !remaining.is_empty() {
        let placeholders: String = remaining.iter().map(|_| "?").collect::<Vec<_>>().join(",");
        let params: Vec<i64> = remaining.iter().map(|&id| id as i64).collect();
        let param_refs: Vec<&dyn rusqlite::types::ToSql> = params
            .iter()
            .map(|p| p as &dyn rusqlite::types::ToSql)
            .collect();

        let sql = format!(
            "SELECT entry, RequiredReputationFaction, RequiredReputationRank FROM item_template WHERE entry IN ({placeholders}) AND RequiredReputationFaction > 0"
        );
        if let Ok(mut stmt) = conn.prepare(&sql) {
            if let Ok(rows) = stmt.query_map(param_refs.as_slice(), |row| {
                Ok((
                    row.get::<_, u32>(0)?,
                    row.get::<_, u32>(1)?,
                    row.get::<_, u32>(2)?,
                ))
            }) {
                for row in rows.flatten() {
                    let (item_id, faction_id, rank_id) = row;
                    if !remaining.contains(&item_id) {
                        continue;
                    }
                    let faction_name: String = conn
                        .query_row(
                            "SELECT FactionName1 FROM faction_store WHERE Entry=?",
                            [faction_id],
                            |row| row.get(0),
                        )
                        .unwrap_or_else(|_| format!("Faction {faction_id}"));
                    let rank_name = rep_rank_name(rank_id);
                    sources.insert(item_id, format!("{faction_name} - {rank_name}"));
                    remaining.remove(&item_id);
                }
            }
        }
    }

    // Step 3: Badge and PvP vendors (npc_vendor)
    if !remaining.is_empty() {
        let placeholders: String = remaining.iter().map(|_| "?").collect::<Vec<_>>().join(",");
        let params: Vec<i64> = remaining.iter().map(|&id| id as i64).collect();
        let param_refs: Vec<&dyn rusqlite::types::ToSql> = params
            .iter()
            .map(|p| p as &dyn rusqlite::types::ToSql)
            .collect();

        let sql = format!(
            "SELECT item, entry, ExtendedCost FROM npc_vendor WHERE item IN ({placeholders})"
        );
        let mut vendor_rows: HashMap<u32, Vec<(u32, u32)>> = HashMap::new();
        if let Ok(mut stmt) = conn.prepare(&sql) {
            if let Ok(rows) = stmt.query_map(param_refs.as_slice(), |row| {
                Ok((
                    row.get::<_, u32>(0)?,
                    row.get::<_, u32>(1)?,
                    row.get::<_, u32>(2)?,
                ))
            }) {
                for row in rows.flatten() {
                    vendor_rows.entry(row.0).or_default().push((row.1, row.2));
                }
            }
        }

        for (item_id, vendors) in &vendor_rows {
            if !remaining.contains(item_id) {
                continue;
            }
            // Check badge vendors first
            let mut found = false;
            for &(vendor_id, _) in vendors {
                if BADGE_VENDORS.contains(&vendor_id) {
                    sources.insert(*item_id, "Badge of Justice Vendor".to_string());
                    remaining.remove(item_id);
                    found = true;
                    break;
                }
            }
            if found {
                continue;
            }
            // Check PvP/tier vendors
            for &(vendor_id, _) in vendors {
                let Ok(vname) = conn.query_row(
                    "SELECT name FROM creature_template WHERE entry=?",
                    [vendor_id],
                    |row| row.get::<_, String>(0),
                ) else {
                    continue;
                };
                let vname_lower = vname.to_lowercase();
                if PVP_VENDOR_KEYWORDS
                    .iter()
                    .any(|kw| vname_lower.contains(kw))
                {
                    sources.insert(*item_id, "PvP Vendor".to_string());
                    remaining.remove(item_id);
                    break;
                }
                // Tier token vendor
                if let Some((_boss, _inst)) = TIER_TOKEN_SOURCES
                    .iter()
                    .find(|s| s.vendor_name == vname_lower)
                    .and_then(|_| {
                        let inv_type: u32 = conn
                            .query_row(
                                "SELECT InventoryType FROM item_template WHERE entry=?",
                                [*item_id],
                                |row| row.get(0),
                            )
                            .ok()?;
                        tier_token_source(&vname_lower, inv_type)
                    })
                {
                    sources.insert(*item_id, format!("Drop: {_boss} - {_inst} (Tier Token)"));
                    remaining.remove(item_id);
                    break;
                } else if TIER_TOKEN_SOURCES
                    .iter()
                    .any(|s| s.vendor_name == vname_lower)
                {
                    sources.insert(*item_id, format!("Vendor: {vname}"));
                    remaining.remove(item_id);
                    break;
                }
            }
        }
    }

    // Step 4: Tier set / PvP vendors (npc_vendor_template)
    if !remaining.is_empty() {
        let placeholders: String = remaining.iter().map(|_| "?").collect::<Vec<_>>().join(",");
        let params: Vec<i64> = remaining.iter().map(|&id| id as i64).collect();
        let param_refs: Vec<&dyn rusqlite::types::ToSql> = params
            .iter()
            .map(|p| p as &dyn rusqlite::types::ToSql)
            .collect();

        let sql = format!(
            "SELECT item, entry, ExtendedCost FROM npc_vendor_template WHERE item IN ({placeholders})"
        );
        let mut template_rows: HashMap<u32, Vec<(u32, u32)>> = HashMap::new();
        if let Ok(mut stmt) = conn.prepare(&sql) {
            if let Ok(rows) = stmt.query_map(param_refs.as_slice(), |row| {
                Ok((
                    row.get::<_, u32>(0)?,
                    row.get::<_, u32>(1)?,
                    row.get::<_, u32>(2)?,
                ))
            }) {
                for row in rows.flatten() {
                    template_rows.entry(row.0).or_default().push((row.1, row.2));
                }
            }
        }

        for (item_id, templates) in &template_rows {
            if !remaining.contains(item_id) {
                continue;
            }
            for &(template_id, _) in templates {
                let Ok(vname) = conn.query_row(
                    "SELECT name FROM creature_template WHERE VendorTemplateId=? LIMIT 1",
                    [template_id],
                    |row| row.get::<_, String>(0),
                ) else {
                    continue;
                };
                let vendor_lower = vname.to_lowercase();
                if PVP_VENDOR_KEYWORDS
                    .iter()
                    .any(|kw| vendor_lower.contains(kw))
                {
                    sources.insert(*item_id, "PvP Vendor".to_string());
                } else if let Some((boss, inst)) = TIER_TOKEN_SOURCES
                    .iter()
                    .find(|s| s.vendor_name == vendor_lower)
                    .and_then(|_| {
                        let inv_type: u32 = conn
                            .query_row(
                                "SELECT InventoryType FROM item_template WHERE entry=?",
                                [*item_id],
                                |row| row.get(0),
                            )
                            .ok()?;
                        tier_token_source(&vendor_lower, inv_type)
                    })
                {
                    sources.insert(*item_id, format!("Drop: {boss} - {inst} (Tier Token)"));
                } else {
                    sources.insert(*item_id, format!("Vendor: {vname}"));
                }
                remaining.remove(item_id);
                break;
            }
        }
    }

    // Step 5: Quest rewards
    if !remaining.is_empty() {
        let placeholders: String = remaining.iter().map(|_| "?").collect::<Vec<_>>().join(",");
        let params: Vec<i64> = remaining.iter().map(|&id| id as i64).collect();
        let _param_refs: Vec<&dyn rusqlite::types::ToSql> = params
            .iter()
            .map(|p| p as &dyn rusqlite::types::ToSql)
            .collect();

        // Build WHERE clause checking all reward columns
        let mut all_params: Vec<i64> = Vec::new();
        let mut conditions = Vec::new();
        for col in &[
            "RewChoiceItemId1",
            "RewChoiceItemId2",
            "RewChoiceItemId3",
            "RewChoiceItemId4",
            "RewItemId1",
            "RewItemId2",
            "RewItemId3",
            "RewItemId4",
        ] {
            conditions.push(format!("{col} IN ({placeholders})"));
            all_params.extend_from_slice(&params);
        }
        let sql = format!(
            "SELECT Title, RewChoiceItemId1, RewChoiceItemId2, RewChoiceItemId3, RewChoiceItemId4, RewItemId1, RewItemId2, RewItemId3, RewItemId4 FROM quest_template WHERE {}",
            conditions.join(" OR ")
        );
        let all_refs: Vec<&dyn rusqlite::types::ToSql> = all_params
            .iter()
            .map(|p| p as &dyn rusqlite::types::ToSql)
            .collect();
        if let Ok(mut stmt) = conn.prepare(&sql) {
            if let Ok(rows) = stmt.query_map(all_refs.as_slice(), |row| {
                let title: String = row.get(0)?;
                let mut reward_ids: Vec<u32> = Vec::new();
                for i in 1..=8 {
                    let id: u32 = row.get(i).unwrap_or(0);
                    if id != 0 {
                        reward_ids.push(id);
                    }
                }
                Ok((title, reward_ids))
            }) {
                for row in rows.flatten() {
                    let (title, reward_ids) = row;
                    for id in reward_ids {
                        if remaining.contains(&id) {
                            sources.insert(id, format!("Quest: {title}"));
                            remaining.remove(&id);
                        }
                    }
                }
            }
        }
    }

    // Step 6: Crafted items
    if !remaining.is_empty() {
        let placeholders: String = remaining.iter().map(|_| "?").collect::<Vec<_>>().join(",");
        let params: Vec<i64> = remaining.iter().map(|&id| id as i64).collect();
        let param_refs: Vec<&dyn rusqlite::types::ToSql> = params
            .iter()
            .map(|p| p as &dyn rusqlite::types::ToSql)
            .collect();

        let sql = format!(
            "SELECT EffectItemType1 FROM spell_template WHERE EffectItemType1 IN ({placeholders})"
        );
        if let Ok(mut stmt) = conn.prepare(&sql) {
            if let Ok(rows) = stmt.query_map(param_refs.as_slice(), |row| row.get::<_, u32>(0)) {
                for id in rows.flatten() {
                    sources.insert(id, "Profession: Crafted".to_string());
                    remaining.remove(&id);
                }
            }
        }
    }

    // Step 7: BoE world drops
    if !remaining.is_empty() {
        let placeholders: String = remaining.iter().map(|_| "?").collect::<Vec<_>>().join(",");
        let params: Vec<i64> = remaining.iter().map(|&id| id as i64).collect();
        let param_refs: Vec<&dyn rusqlite::types::ToSql> = params
            .iter()
            .map(|p| p as &dyn rusqlite::types::ToSql)
            .collect();

        let sql =
            format!("SELECT entry, bonding FROM item_template WHERE entry IN ({placeholders})");
        if let Ok(mut stmt) = conn.prepare(&sql) {
            if let Ok(rows) = stmt.query_map(param_refs.as_slice(), |row| {
                Ok((row.get::<_, u32>(0)?, row.get::<_, u32>(1)?))
            }) {
                for row in rows.flatten() {
                    if row.1 == 2 {
                        sources.insert(row.0, "Auction House - BoE World Drop".to_string());
                        remaining.remove(&row.0);
                    }
                }
            }
        }
    }

    // Anything left
    for &item_id in &remaining {
        sources.insert(item_id, "Other (Classic, Seasonal Event, Etc.)".to_string());
    }

    sources
}

// ---------------------------------------------------------------------------
// Lua parsing
// ---------------------------------------------------------------------------

fn parse_spec_from_lua(lua_text: &str, spec_key: &str) -> HashMap<String, Vec<u32>> {
    let pattern = format!(
        r#"data\["{key}"\]\s*=\s*\{{"#,
        key = regex::escape(spec_key)
    );
    let block_re = Regex::new(&pattern).expect("invariant: valid regex");
    let Some(m) = block_re.find(lua_text) else {
        return HashMap::new();
    };
    let block_start = m.end();
    let data_marker = Regex::new(r#"data\[""#).expect("invariant: valid regex");
    let block_end = data_marker
        .find(&lua_text[block_start..])
        .map(|m2| block_start + m2.start())
        .unwrap_or(lua_text.len());
    let block = &lua_text[block_start..block_end];

    let slot_re =
        Regex::new(r#"format\(AL\["([^"]+)"\][^}]*\[NORMAL_DIFF\]\s*=\s*\{(.*?\})\s*,\s*\}"#)
            .expect("invariant: valid regex");
    let item_re = Regex::new(r"\{\s*\d+\s*,\s*(\d+)\s*\}").expect("invariant: valid regex");

    let mut slots: HashMap<String, Vec<u32>> = HashMap::new();

    for slot_match in slot_re.captures_iter(block) {
        let al_name = &slot_match[1];
        let items_text = &slot_match[2];

        let canonical = SLOT_MAP
            .iter()
            .find(|(k, _)| *k == al_name)
            .map(|(_, v)| *v);
        let Some(canonical) = canonical else {
            continue;
        };

        let item_ids: Vec<u32> = item_re
            .captures_iter(items_text)
            .filter_map(|c| c[1].parse().ok())
            .collect();

        if let Some(existing) = slots.get_mut(canonical) {
            // Interleave for fair ranking (e.g. Main Hand + Twohand → weapons)
            let mut combined = Vec::new();
            let (mut i, mut j) = (0, 0);
            while i < existing.len() || j < item_ids.len() {
                if i < existing.len() {
                    combined.push(existing[i]);
                    i += 1;
                }
                if j < item_ids.len() {
                    combined.push(item_ids[j]);
                    j += 1;
                }
            }
            *existing = combined;
        } else {
            slots.insert(canonical.to_string(), item_ids);
        }
    }

    slots
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

pub fn run(spec: &str, output_override: Option<&str>) -> Result<()> {
    let root = common::project_root()?;
    let current_phase = common::load_current_phase(&root)?;

    let lua_keys = SPEC_LUA_KEYS
        .iter()
        .find(|(s, _)| *s == spec)
        .map(|(_, keys)| *keys)
        .context(format!("No AtlasLoot key mapping for spec '{spec}'"))?;

    let sources_dir = root.join("sources").join("atlasloot");
    let db_path = common::db_path(&root);

    let conn = if db_path.exists() {
        Some(Connection::open(&db_path)?)
    } else {
        None
    };

    // Collect all phase data and item IDs
    let mut all_phase_data: Vec<(String, HashMap<String, Vec<u32>>)> = Vec::new();
    let mut all_item_ids: HashSet<u32> = HashSet::new();

    for &(lua_filename, spec_lua_key) in lua_keys {
        let phase_key = PHASE_MAP
            .iter()
            .find(|(f, _)| *f == lua_filename)
            .map(|(_, p)| p.to_string())
            .unwrap_or_default();

        // Find lua file in atlasloot subdirs
        let mut lua_path = None;
        if let Ok(entries) = std::fs::read_dir(&sources_dir) {
            for entry in entries.flatten() {
                let candidate = entry.path().join(lua_filename);
                if candidate.exists() {
                    lua_path = Some(candidate);
                    break;
                }
            }
        }

        let Some(lua_path) = lua_path else {
            println!("Warning: {lua_filename} not found, skipping {phase_key}");
            continue;
        };

        let lua_text = std::fs::read_to_string(&lua_path)?;
        let slots = parse_spec_from_lua(&lua_text, spec_lua_key);

        if slots.is_empty() {
            println!("Warning: spec key '{spec_lua_key}' not found in {lua_filename}");
            continue;
        }

        for ids in slots.values() {
            all_item_ids.extend(ids);
        }
        all_phase_data.push((phase_key, slots));
    }

    // Bulk load from DB
    let item_info = conn
        .as_ref()
        .map(|c| load_item_info(c, &all_item_ids))
        .unwrap_or_default();
    let item_sources = conn
        .as_ref()
        .map(|c| classify_item_sources(c, &all_item_ids, &root))
        .unwrap_or_default();

    // Build output
    let mut phases: IndexMap<String, IndexMap<String, Vec<ParsedItem>>> = IndexMap::new();

    for (phase_key, slots) in &all_phase_data {
        let mut phase_slots: IndexMap<String, Vec<ParsedItem>> = IndexMap::new();

        for (slot_key, item_ids) in slots {
            let mut items: Vec<ParsedItem> = Vec::new();
            let mut seen: HashSet<u32> = HashSet::new();
            let mut rank_idx = 0u32;

            for &item_id in item_ids {
                if seen.contains(&item_id) {
                    continue;
                }
                seen.insert(item_id);

                // Skip non-equippable
                if let Some(info) = item_info.get(&item_id) {
                    if info.1 == 0 {
                        continue;
                    }
                }

                if rank_idx >= 5 {
                    break;
                }

                let rank = if rank_idx < 1 { "BiS" } else { "Optional" };

                let name = item_info
                    .get(&item_id)
                    .map(|(n, _)| n.clone())
                    .unwrap_or_else(|| format!("Unknown ({item_id})"));
                let source = item_sources
                    .get(&item_id)
                    .cloned()
                    .unwrap_or_else(|| "Unknown".to_string());

                // Filter out seasonal/classic
                if source.starts_with("Other (Classic") {
                    continue; // Don't count toward rank limit
                }

                rank_idx += 1;
                items.push(ParsedItem {
                    rank: rank.to_string(),
                    name,
                    source,
                    item_id: Some(item_id),
                });
            }

            phase_slots.insert(slot_key.clone(), items);
        }

        let slot_count = phase_slots.len();
        let item_count: usize = phase_slots.values().map(|v| v.len()).sum();
        println!("  {phase_key}: {slot_count} slots, {item_count} items");
        phases.insert(phase_key.clone(), phase_slots);
    }

    let output = ParsedOutput {
        current_phase,
        phases: phases.clone(),
    };

    let output_path = match output_override {
        Some(p) => std::path::PathBuf::from(p),
        None => root.join("output").join(spec).join("al_bis_gear.json"),
    };
    write_output(&output, &output_path)?;
    println!("\nWrote {}", output_path.display());

    Ok(())
}
