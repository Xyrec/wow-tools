use anyhow::{bail, Context, Result};
use regex::Regex;
use serde::Deserialize;
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

pub const PRIMAL_NETHER: u32 = 23572;
pub const LARGE_PRISMATIC_SHARD: u32 = 22449;
pub const VOID_CRYSTAL: u32 = 22450;
pub const AH_KEEP: f64 = 0.95; // seller keeps 95% after AH cut

#[derive(Default, Clone, Copy)]
pub struct ItemPrices {
    pub horde_mv: Option<u64>,
    pub alliance_mv: Option<u64>,
    pub region_mv: Option<u64>,
    pub region_sold_per_day: Option<f64>,
}

pub struct Market {
    pub items: HashMap<u32, ItemPrices>,
    pub vendor: HashMap<u32, u64>,
}

impl Market {
    /// Acquisition cost per unit in copper: Horde MV -> Alliance MV -> region MV -> vendor.
    pub fn mat_price(&self, id: u32) -> Option<f64> {
        let p = self.items.get(&id).copied().unwrap_or_default();
        p.horde_mv
            .or(p.alliance_mv)
            .or(p.region_mv)
            .map(|c| c as f64)
            .or_else(|| self.vendor.get(&id).map(|&c| c as f64))
    }

    pub fn horde_mv(&self, id: u32) -> Option<f64> {
        self.items.get(&id).and_then(|p| p.horde_mv).map(|c| c as f64)
    }

    pub fn sold_per_day(&self, id: u32) -> f64 {
        self.items
            .get(&id)
            .and_then(|p| p.region_sold_per_day)
            .unwrap_or(0.0)
    }
}

pub fn parse_appdata(path: &Path) -> Result<HashMap<u32, ItemPrices>> {
    let text = std::fs::read_to_string(path)
        .with_context(|| format!("reading {}", path.display()))?;
    let section_re = Regex::new(r#"(?s)LoadData\("([A-Z_]+)","([^"]+)",\[\[(.*?)\]\]\)"#)?;
    let fields_re = Regex::new(r"fields=\{([^}]*)\}")?;
    let row_re = Regex::new(r"\{(\d+),([0-9A-V][0-9A-V,]*)\}")?;

    let mut items: HashMap<u32, ItemPrices> = HashMap::new();
    for cap in section_re.captures_iter(&text) {
        let (typ, realm, body) = (&cap[1], &cap[2], &cap[3]);
        if typ == "APP_INFO" {
            continue;
        }
        let fields: Vec<String> = fields_re
            .captures(body)
            .context("section without fields")?[1]
            .split(',')
            .skip(1) // first field is itemString (the row key)
            .map(|f| f.trim_matches('"').to_string())
            .collect();
        for row in row_re.captures_iter(body) {
            let id: u32 = row[1].parse()?;
            let vals: Vec<u64> = row[2]
                .split(',')
                .map(|v| u64::from_str_radix(v, 32))
                .collect::<Result<_, _>>()?;
            let entry = items.entry(id).or_default();
            for (name, val) in fields.iter().zip(vals) {
                match (realm, name.as_str()) {
                    ("Thunderstrike-Horde", "marketValue") => entry.horde_mv = Some(val),
                    ("Thunderstrike-Alliance", "marketValue") => entry.alliance_mv = Some(val),
                    (_, "regionMarketValue") => entry.region_mv = Some(val),
                    (_, "regionSoldPerDay") => {
                        entry.region_sold_per_day = Some(val as f64 / 1000.0)
                    }
                    _ => {}
                }
            }
        }
    }
    if items.is_empty() {
        bail!("no market data parsed from {}", path.display());
    }
    Ok(items)
}

pub fn parse_vendor(path: &Path) -> Result<HashMap<u32, u64>> {
    let text = std::fs::read_to_string(path)
        .with_context(|| format!("reading {}", path.display()))?;
    let re = Regex::new(r#"\["i:(\d+)"\] = (\d+)"#)?;
    Ok(re
        .captures_iter(&text)
        .map(|c| (c[1].parse().unwrap(), c[2].parse().unwrap()))
        .collect())
}

#[derive(Deserialize)]
pub struct RawRecipe {
    pub profession: u32,
    pub name: String,
    pub productid: u32,
    pub nummade: u32,
    pub reagents: Vec<Reagent>,
}

#[derive(Deserialize)]
pub struct Reagent {
    pub id: u32,
    pub num: u32,
}

#[derive(Deserialize, Clone)]
pub struct Dungeon {
    pub name: String,
    pub bosses: u32,
}

#[derive(Clone)]
pub struct Craft {
    pub name: String,
    pub nethers: u32,
    pub mat_cost: f64,      // copper, nether excluded
    pub unit_revenue: f64,  // copper, after AH cut
    pub profit: f64,        // copper per craft
    pub profit_per_nether: f64,
    pub region_sold_per_day: f64,
}

fn profession_name(id: u32) -> String {
    match id {
        164 => "Blacksmithing",
        165 => "Leatherworking",
        171 => "Alchemy",
        197 => "Tailoring",
        202 => "Engineering",
        333 => "Enchanting",
        755 => "Jewelcrafting",
        _ => return format!("profession-{id}"),
    }
    .to_string()
}

/// Build per-profession lists of profitable, AH-sellable nether crafts,
/// sorted by profit per nether (desc).
pub fn build_crafts(
    recipes: &[RawRecipe],
    market: &Market,
) -> BTreeMap<String, Vec<Craft>> {
    let mut out: BTreeMap<String, Vec<Craft>> = BTreeMap::new();
    for r in recipes {
        let Some(mv) = market.horde_mv(r.productid) else {
            continue; // unlisted => BoP or dead market
        };
        let mut mat_cost = 0.0;
        let mut nethers = 0;
        let mut missing = false;
        for reg in &r.reagents {
            if reg.id == PRIMAL_NETHER {
                nethers = reg.num;
                continue;
            }
            match market.mat_price(reg.id) {
                Some(p) => mat_cost += p * reg.num as f64,
                None => missing = true,
            }
        }
        if missing || nethers == 0 {
            continue;
        }
        let unit_revenue = mv * r.nummade as f64 * AH_KEEP;
        let profit = unit_revenue - mat_cost;
        if profit <= 0.0 {
            continue;
        }
        out.entry(profession_name(r.profession)).or_default().push(Craft {
            name: r.name.clone(),
            nethers,
            mat_cost,
            unit_revenue,
            profit,
            profit_per_nether: profit / nethers as f64,
            region_sold_per_day: market.sold_per_day(r.productid),
        });
    }
    for crafts in out.values_mut() {
        crafts.sort_by(|a, b| b.profit_per_nether.total_cmp(&a.profit_per_nether));
    }
    out.retain(|_, v| !v.is_empty());
    out
}
