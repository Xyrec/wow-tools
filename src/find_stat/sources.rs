use std::collections::HashSet;

use rusqlite::Connection;

use crate::lookup::{ARMOR_SUBCLASS, SOCKET_COLORS};

static REP_RANK_NAMES: &[(u32, &str)] = &[
    (0, "None"),
    (1, "Hated"),
    (2, "Hostile"),
    (3, "Unfriendly"),
    (4, "Friendly"),
    (5, "Honored"),
    (6, "Revered"),
    (7, "Exalted"),
];

pub fn rep_rank_name(rank: u32) -> &'static str {
    REP_RANK_NAMES
        .iter()
        .find(|(id, _)| *id == rank)
        .map(|(_, name)| *name)
        .unwrap_or("?")
}

pub fn get_faction_name(conn: &Connection, faction_id: u32) -> String {
    conn.query_row(
        "SELECT FactionName1 FROM faction_store WHERE Entry=?",
        [faction_id],
        |row| row.get::<_, String>(0),
    )
    .unwrap_or_else(|_| format!("Faction {faction_id}"))
}

pub fn get_stat_value(conn: &Connection, item_id: u32, stat_type_id: u32) -> i32 {
    let cols: String = (1..=10)
        .map(|i| format!("stat_type{i},stat_value{i}"))
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!("SELECT {cols} FROM item_template WHERE entry=?");
    let result = conn.query_row(&sql, [item_id], |row| {
        let mut total = 0i32;
        for i in 0..10 {
            let st: u32 = row.get(i * 2)?;
            let sv: i32 = row.get(i * 2 + 1)?;
            if st == stat_type_id {
                total += sv;
            }
        }
        Ok(total)
    });
    result.unwrap_or(0)
}

pub fn get_instance_type(conn: &Connection, creature_id: u32) -> &'static str {
    let maps: Vec<u32> = {
        let mut stmt = conn
            .prepare("SELECT DISTINCT map FROM creature WHERE id=?")
            .unwrap();
        stmt.query_map([creature_id], |row| row.get(0))
            .unwrap()
            .filter_map(|r| r.ok())
            .collect()
    };
    for map_id in maps {
        if let Ok(max_players) = conn.query_row(
            "SELECT maxPlayers FROM instance_template WHERE map=?",
            [map_id],
            |row| row.get::<_, u32>(0),
        ) {
            if max_players <= 5 {
                return "dungeon";
            }
            if max_players <= 10 {
                return "raid10";
            }
            return "raid";
        }
    }
    "world"
}

pub fn is_heroic_creature(conn: &Connection, creature_id: u32) -> bool {
    conn.query_row(
        "SELECT COUNT(*) FROM creature_template WHERE HeroicEntry=?",
        [creature_id],
        |row| row.get::<_, u32>(0),
    )
    .unwrap_or(0)
        > 0
}

#[derive(Debug, Clone)]
pub struct DropSource {
    pub creature_name: String,
    pub instance_type: String,
    pub is_heroic: bool,
}

#[derive(Debug, Clone)]
pub struct VendorSource {
    pub vendor_name: String,
}

#[derive(Debug, Clone)]
pub enum ItemSource {
    Drop(DropSource),
    Vendor(VendorSource),
}

pub fn get_item_sources(conn: &Connection, item_id: u32) -> Vec<ItemSource> {
    let mut sources = Vec::new();

    // Direct creature loot
    {
        let mut stmt = conn
            .prepare(
                "SELECT clt.entry, ct.Name, clt.ChanceOrQuestChance
             FROM creature_loot_template clt
             JOIN creature_template ct ON ct.entry = clt.entry
             WHERE clt.item = ? ORDER BY clt.ChanceOrQuestChance DESC",
            )
            .unwrap();
        let rows: Vec<(u32, String, f64)> = stmt
            .query_map([item_id], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))
            .unwrap()
            .filter_map(|r| r.ok())
            .collect();
        for (cid, name, chance) in rows {
            if chance <= 0.0 {
                continue;
            }
            sources.push(ItemSource::Drop(DropSource {
                creature_name: name.trim_end_matches(" (1)").to_string(),
                instance_type: get_instance_type(conn, cid).to_string(),
                is_heroic: is_heroic_creature(conn, cid),
            }));
        }
    }

    // Reference loot
    {
        let mut stmt = conn
            .prepare("SELECT entry FROM reference_loot_template WHERE item = ?")
            .unwrap();
        let ref_ids: Vec<u32> = stmt
            .query_map([item_id], |row| row.get(0))
            .unwrap()
            .filter_map(|r| r.ok())
            .collect();
        for ref_id in ref_ids {
            let mut stmt2 = conn
                .prepare(
                    "SELECT clt.entry, ct.Name, clt.ChanceOrQuestChance
                 FROM creature_loot_template clt
                 JOIN creature_template ct ON ct.entry = clt.entry
                 WHERE clt.mincountOrRef = ? ORDER BY clt.ChanceOrQuestChance DESC",
                )
                .unwrap();
            let rows: Vec<(u32, String, f64)> = stmt2
                .query_map([-(ref_id as i64)], |row| {
                    Ok((row.get(0)?, row.get(1)?, row.get(2)?))
                })
                .unwrap()
                .filter_map(|r| r.ok())
                .collect();
            for (cid, name, _chance) in rows {
                sources.push(ItemSource::Drop(DropSource {
                    creature_name: name.trim_end_matches(" (1)").to_string(),
                    instance_type: get_instance_type(conn, cid).to_string(),
                    is_heroic: is_heroic_creature(conn, cid),
                }));
            }
        }
    }

    // Vendor tables
    {
        let mut stmt = conn
            .prepare(
                "SELECT ct.Name FROM npc_vendor nv
             JOIN creature_template ct ON ct.entry = nv.entry
             WHERE nv.item = ?",
            )
            .unwrap();
        let rows: Vec<String> = stmt
            .query_map([item_id], |row| row.get(0))
            .unwrap()
            .filter_map(|r| r.ok())
            .collect();
        for name in rows {
            sources.push(ItemSource::Vendor(VendorSource { vendor_name: name }));
        }
    }

    // npc_vendor_template
    {
        let mut stmt = conn
            .prepare("SELECT entry FROM npc_vendor_template WHERE item = ?")
            .unwrap();
        let template_ids: Vec<u32> = stmt
            .query_map([item_id], |row| row.get(0))
            .unwrap()
            .filter_map(|r| r.ok())
            .collect();
        for tid in template_ids {
            let mut stmt2 = conn
                .prepare("SELECT Name FROM creature_template WHERE VendorTemplateId=?")
                .unwrap();
            let names: Vec<String> = stmt2
                .query_map([tid], |row| row.get(0))
                .unwrap()
                .filter_map(|r| r.ok())
                .collect();
            for name in names {
                sources.push(ItemSource::Vendor(VendorSource { vendor_name: name }));
            }
        }
    }

    sources
}

pub fn classify_source(bonding: u32, rep_faction: u32, sources: &[ItemSource]) -> &'static str {
    if bonding == 2 {
        return "boe";
    }
    if rep_faction > 0 {
        return "rep";
    }

    let mut has_dungeon = false;
    let mut has_raid = false;
    let mut has_drop = false;
    for src in sources {
        if let ItemSource::Drop(d) = src {
            has_drop = true;
            match d.instance_type.as_str() {
                "dungeon" => has_dungeon = true,
                "raid" | "raid10" => has_raid = true,
                _ => {}
            }
        }
    }

    if has_dungeon {
        return "dungeon";
    }
    if has_raid {
        return "raid";
    }
    if has_drop {
        return "drop";
    }
    if !sources.is_empty() {
        return "vendor";
    }
    "other"
}

pub fn format_source(
    conn: &Connection,
    classification: &str,
    rep_faction: u32,
    rep_rank: u32,
    sources: &[ItemSource],
) -> String {
    let mut parts: Vec<String> = Vec::new();

    if classification == "boe" {
        parts.push("BoE".to_string());
    } else if classification == "rep" {
        let rank = rep_rank_name(rep_rank);
        let faction = get_faction_name(conn, rep_faction);
        parts.push(format!("Rep: {faction} ({rank})"));
    }

    let mut seen_creatures: HashSet<String> = HashSet::new();
    for src in sources {
        if parts.len() >= 2 {
            break;
        }
        match src {
            ItemSource::Drop(d) => {
                if seen_creatures.contains(&d.creature_name) {
                    continue;
                }
                seen_creatures.insert(d.creature_name.clone());
                let mut label = d.creature_name.clone();
                if d.is_heroic {
                    label.push_str(" (H)");
                }
                match d.instance_type.as_str() {
                    "dungeon" => label = format!("Dungeon: {label}"),
                    "raid" | "raid10" => label = format!("Raid: {label}"),
                    _ => {}
                }
                parts.push(label);
            }
            ItemSource::Vendor(v) => {
                if classification != "boe" && classification != "rep" {
                    parts.push(format!("Vendor: {}", v.vendor_name));
                }
            }
        }
    }

    if parts.is_empty() {
        "unknown".to_string()
    } else {
        parts.join(" | ")
    }
}

pub fn armor_subclass_name(subclass: u32) -> &'static str {
    ARMOR_SUBCLASS
        .iter()
        .find(|(id, _)| *id == subclass)
        .map(|(_, name)| *name)
        .unwrap_or("")
}

pub fn socket_color_name(color_id: u32) -> &'static str {
    SOCKET_COLORS
        .iter()
        .find(|(id, _)| *id == color_id)
        .map(|(_, name)| *name)
        .unwrap_or("")
}
