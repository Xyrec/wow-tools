pub mod aura;
pub mod display;

use anyhow::{Context, Result};
use rusqlite::Connection;
use std::collections::HashMap;

use crate::common;

// ---------------------------------------------------------------------------
// Constant maps (mirror Python's dictionaries)
// ---------------------------------------------------------------------------

pub static STAT_TYPE_NAMES: &[(u32, &str)] = &[
    (0, "(none)"),
    (1, "Health"),
    (3, "Agility"),
    (4, "Strength"),
    (5, "Intellect"),
    (6, "Spirit"),
    (7, "Stamina"),
    (12, "Defense Rating"),
    (13, "Dodge Rating"),
    (14, "Parry Rating"),
    (15, "Block Rating"),
    (16, "Melee Hit Rating"),
    (17, "Ranged Hit Rating"),
    (18, "Spell Hit Rating"),
    (19, "Melee Crit Rating"),
    (20, "Ranged Crit Rating"),
    (21, "Spell Crit Rating"),
    (31, "Hit Rating"),
    (32, "Crit Rating"),
    (35, "Resilience"),
    (36, "Haste Rating"),
    (37, "Expertise Rating"),
    (38, "Attack Power"),
    (39, "Ranged Attack Power"),
    (41, "+Healing (deprecated WotLK)"),
    (42, "+Spell Damage (deprecated WotLK)"),
    (43, "MP5"),
    (44, "Armor Penetration"),
    (45, "Spell Power"),
    (46, "Health per 5"),
    (47, "Spell Penetration"),
];

pub static INVENTORY_TYPES: &[(u32, &str)] = &[
    (0, "Non-equippable"),
    (1, "Head"),
    (2, "Neck"),
    (3, "Shoulder"),
    (4, "Shirt"),
    (5, "Chest"),
    (6, "Waist"),
    (7, "Legs"),
    (8, "Feet"),
    (9, "Wrist"),
    (10, "Hands"),
    (11, "Finger"),
    (12, "Trinket"),
    (13, "One-Hand"),
    (14, "Shield"),
    (15, "Ranged"),
    (16, "Back"),
    (17, "Two-Hand"),
    (18, "Bag"),
    (20, "Chest (robe)"),
    (21, "Main Hand"),
    (22, "Off Hand"),
    (23, "Held In Off-Hand"),
    (24, "Ammo"),
    (25, "Thrown"),
    (26, "Ranged (gun/wand)"),
    (28, "Relic"),
];

pub static ARMOR_SUBCLASS: &[(u32, &str)] = &[
    (0, "Misc"),
    (1, "Cloth"),
    (2, "Leather"),
    (3, "Mail"),
    (4, "Plate"),
    (5, "Buckler (obsolete)"),
    (6, "Shield"),
    (7, "Libram"),
    (8, "Idol"),
    (9, "Totem"),
];

pub static WEAPON_SUBCLASS: &[(u32, &str)] = &[
    (0, "Axe (1H)"),
    (1, "Axe (2H)"),
    (2, "Bow"),
    (3, "Gun"),
    (4, "Mace (1H)"),
    (5, "Mace (2H)"),
    (6, "Polearm"),
    (7, "Sword (1H)"),
    (8, "Sword (2H)"),
    (10, "Staff"),
    (11, "Exotic (1H)"),
    (13, "Fist Weapon"),
    (14, "Misc"),
    (15, "Dagger"),
    (16, "Thrown"),
    (17, "Spear"),
    (18, "Crossbow"),
    (19, "Wand"),
    (20, "Fishing Pole"),
];

pub static DAMAGE_SCHOOL: &[(u32, &str)] = &[
    (0, "Physical"),
    (1, "Holy"),
    (2, "Fire"),
    (3, "Nature"),
    (4, "Frost"),
    (5, "Shadow"),
    (6, "Arcane"),
];

pub static RESISTANCE_FIELDS: &[(&str, &str)] = &[
    ("holy_res", "Holy Resistance"),
    ("fire_res", "Fire Resistance"),
    ("nature_res", "Nature Resistance"),
    ("frost_res", "Frost Resistance"),
    ("shadow_res", "Shadow Resistance"),
    ("arcane_res", "Arcane Resistance"),
];

pub static SOCKET_COLORS: &[(u32, &str)] = &[(1, "Meta"), (2, "Red"), (4, "Yellow"), (8, "Blue")];

fn lookup_map<'a>(table: &'a [(u32, &'a str)], key: u32) -> &'a str {
    table
        .iter()
        .find(|(k, _)| *k == key)
        .map(|(_, v)| *v)
        .unwrap_or("Unknown")
}

// ---------------------------------------------------------------------------
// Item data structures
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct DamageRange {
    pub min: f64,
    pub max: f64,
    pub school: String,
}

#[derive(Debug, Clone)]
pub struct WeaponInfo {
    pub speed: f64,
    pub dps: f64,
    pub damage: Vec<DamageRange>,
}

/// A looked-up item with all its stats.
#[derive(Debug, Clone)]
pub struct ItemData {
    pub id: u32,
    pub name: String,
    pub quality: String,
    pub item_level: u32,
    pub required_level: u32,
    pub slot: String,
    pub item_type: Option<String>,
    pub armor: u32,
    pub block_value: Option<u32>,
    pub weapon: Option<WeaponInfo>,
    pub sockets: Vec<String>,
    pub socket_bonus_id: Option<u32>,
    /// Ordered list of (stat_name, value) to preserve insertion order.
    pub stats: Vec<(String, i32)>,
}

impl ItemData {
    fn stat_value(&self, name: &str) -> i32 {
        self.stats
            .iter()
            .find(|(n, _)| n == name)
            .map(|(_, v)| *v)
            .unwrap_or(0)
    }

    fn add_stat(&mut self, name: &str, value: i32) {
        if let Some(entry) = self.stats.iter_mut().find(|(n, _)| n == name) {
            entry.1 += value;
        } else {
            self.stats.push((name.to_string(), value));
        }
    }
}

// ---------------------------------------------------------------------------
// Spell effect decoding
// ---------------------------------------------------------------------------

fn decode_spell_effects(
    conn: &Connection,
    spell_id: u32,
    aura_names: &HashMap<u32, String>,
) -> Result<Vec<(String, i32)>> {
    let mut stmt = conn.prepare_cached("SELECT * FROM spell_template WHERE Id=?1")?;

    let col_names: Vec<String> = stmt.column_names().iter().map(|c| c.to_string()).collect();

    let row = stmt.query_row([spell_id], |row| {
        let mut values: HashMap<String, f64> = HashMap::new();
        let mut spell_name = String::new();
        for (i, col) in col_names.iter().enumerate() {
            if col == "SpellName" {
                spell_name = row.get::<_, String>(i).unwrap_or_default();
            } else if let Ok(v) = row.get::<_, f64>(i) {
                values.insert(col.clone(), v);
            } else if let Ok(v) = row.get::<_, i64>(i) {
                values.insert(col.clone(), v as f64);
            }
        }
        Ok((values, spell_name))
    });

    let (values, spell_name) = match row {
        Ok(v) => v,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(vec![]),
        Err(e) => return Err(e.into()),
    };

    let mut effects = Vec::new();
    for i in 1..=3 {
        let aura = *values
            .get(&format!("EffectApplyAuraName{i}"))
            .unwrap_or(&0.0) as u32;
        let base = *values.get(&format!("EffectBasePoints{i}")).unwrap_or(&0.0) as i32;
        if aura == 0 || base == 0 {
            continue;
        }
        let value = base + 1; // cmangos stores base-1

        let name = aura_names.get(&aura).cloned().unwrap_or_else(|| {
            if spell_name.is_empty() {
                format!("Aura {aura}")
            } else {
                spell_name.clone()
            }
        });

        effects.push((name, value));
    }
    Ok(effects)
}

// ---------------------------------------------------------------------------
// Core lookup
// ---------------------------------------------------------------------------

/// Look up an item from the cmangos TBC database and return structured data.
pub fn lookup_item(
    conn: &Connection,
    item_id: u32,
    aura_names: &HashMap<u32, String>,
) -> Result<Option<ItemData>> {
    let mut stmt = conn.prepare_cached("SELECT * FROM item_template WHERE entry=?1")?;

    let col_names: Vec<String> = stmt.column_names().iter().map(|c| c.to_string()).collect();

    let row_result = stmt.query_row([item_id], |row| {
        let mut values: HashMap<String, f64> = HashMap::new();
        let mut name = String::new();
        for (i, col) in col_names.iter().enumerate() {
            if col == "name" {
                name = row.get::<_, String>(i).unwrap_or_default();
            } else if let Ok(v) = row.get::<_, f64>(i) {
                values.insert(col.clone(), v);
            } else if let Ok(v) = row.get::<_, i64>(i) {
                values.insert(col.clone(), v as f64);
            }
        }
        Ok((values, name))
    });

    let (item, item_name) = match row_result {
        Ok(v) => v,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
        Err(e) => return Err(e.into()),
    };

    let get = |key: &str| -> f64 { *item.get(key).unwrap_or(&0.0) };

    let quality = get("Quality") as u32;
    let item_class = get("class") as u32;
    let subclass = get("subclass") as u32;
    let inventory_type = get("InventoryType") as u32;

    let item_type = if item_class == 4 {
        Some(lookup_map(ARMOR_SUBCLASS, subclass).to_string())
    } else if item_class == 2 {
        Some(lookup_map(WEAPON_SUBCLASS, subclass).to_string())
    } else {
        None
    };

    let armor_val = get("armor") as u32;
    let block_val = get("block") as u32;

    // Weapon damage ranges
    let delay_ms = get("delay") as f64;
    let mut dmg_ranges = Vec::new();
    for i in 1..=5 {
        let dmin = get(&format!("dmg_min{i}")) as f64;
        let dmax = get(&format!("dmg_max{i}")) as f64;
        let dtype = get(&format!("dmg_type{i}")) as u32;
        if dmin > 0.0 || dmax > 0.0 {
            dmg_ranges.push(DamageRange {
                min: dmin,
                max: dmax,
                school: lookup_map(DAMAGE_SCHOOL, dtype).to_string(),
            });
        }
    }

    let weapon = if !dmg_ranges.is_empty() {
        let speed = delay_ms / 1000.0;
        let total_avg: f64 = dmg_ranges.iter().map(|d| (d.min + d.max) / 2.0).sum();
        let dps = if speed > 0.0 { total_avg / speed } else { 0.0 };
        Some(WeaponInfo {
            speed,
            dps: (dps * 10.0).round() / 10.0, // round to 1 decimal
            damage: dmg_ranges,
        })
    } else {
        None
    };

    // Sockets
    let mut sockets = Vec::new();
    for i in 1..=3 {
        let color_id = get(&format!("socketColor_{i}")) as u32;
        if color_id != 0 {
            sockets.push(lookup_map(SOCKET_COLORS, color_id).to_string());
        }
    }
    let socket_bonus_id = {
        let v = get("socketBonus") as u32;
        if v != 0 { Some(v) } else { None }
    };

    let mut result = ItemData {
        id: item_id,
        name: item_name,
        quality: common::types::quality_name(quality).to_string(),
        item_level: get("ItemLevel") as u32,
        required_level: get("RequiredLevel") as u32,
        slot: lookup_map(INVENTORY_TYPES, inventory_type).to_string(),
        item_type,
        armor: armor_val,
        block_value: if block_val != 0 {
            Some(block_val)
        } else {
            None
        },
        weapon,
        sockets,
        socket_bonus_id,
        stats: Vec::new(),
    };

    // Resistances
    for &(col, label) in RESISTANCE_FIELDS {
        let val = get(col) as i32;
        if val != 0 {
            result.stats.push((label.to_string(), val));
        }
    }

    // Stat columns (1-10)
    for i in 1..=10 {
        let st = get(&format!("stat_type{i}")) as u32;
        let sv = get(&format!("stat_value{i}")) as i32;
        if st != 0 && sv != 0 {
            let name = lookup_map(STAT_TYPE_NAMES, st);
            result.add_stat(name, sv);
        }
    }

    // Spell effects (equip triggers: trigger=1)
    for i in 1..=5 {
        let spell_id = get(&format!("spellid_{i}")) as u32;
        let trigger = get(&format!("spelltrigger_{i}")) as u32;
        if spell_id != 0 && trigger == 1 {
            let effects = decode_spell_effects(conn, spell_id, aura_names)?;
            for (stat_name, value) in effects {
                result.add_stat(&stat_name, value);
            }
        }
    }

    // Collapse equal Mod Healing Done / Mod Damage Done
    let healing = result.stat_value("Mod Healing Done");
    let damage = result.stat_value("Mod Damage Done");
    if healing != 0 && damage != 0 && healing == damage {
        result
            .stats
            .retain(|(n, _)| n != "Mod Healing Done" && n != "Mod Damage Done");
        result
            .stats
            .push(("Spell Damage and Healing".to_string(), healing));
    }

    Ok(Some(result))
}

// ---------------------------------------------------------------------------
// Subcommand entry point
// ---------------------------------------------------------------------------

pub fn run(item_ids: &[u32], compare: bool) -> Result<()> {
    let root = common::project_root()?;
    let db = common::db_path(&root);

    if !db.exists() {
        anyhow::bail!(
            "TBC database not found at {}\nDownload from: https://github.com/cmangos/tbc-db/releases",
            db.display()
        );
    }

    let conn = Connection::open(&db)
        .with_context(|| format!("failed to open database {}", db.display()))?;

    let aura_path = root
        .join("sources")
        .join("cmangos-tbc-db")
        .join("src")
        .join("SpellAuraDefines.h");
    let aura_names = aura::load_aura_names(&aura_path)?;

    let mut items = Vec::new();
    for &id in item_ids {
        match lookup_item(&conn, id, &aura_names)? {
            Some(item) => items.push(item),
            None => eprintln!("Item {id} not found in database."),
        }
    }

    if items.is_empty() {
        std::process::exit(1);
    }

    if compare && items.len() >= 2 {
        display::print_compare(&items);
    } else {
        for item in &items {
            display::print_item(item);
        }
    }

    Ok(())
}
