mod data;
mod sim;

use anyhow::{Context, Result};
use clap::Parser;
use data::{Craft, AH_KEEP, LARGE_PRISMATIC_SHARD, VOID_CRYSTAL};
use std::path::PathBuf;

const QUANTILES: &[f64] = &[0.10, 0.25, 0.50, 0.75, 0.90];

/// Monte Carlo simulator: tanking TBC heroics for Primal Nethers + shards,
/// dumping nethers into AH-sellable crafts, per profession.
#[derive(Parser)]
#[command(version, about)]
struct Args {
    /// Simulated horizons per scenario
    #[arg(long, default_value_t = 10_000)]
    iterations: u32,
    /// Days per horizon (long enough that slow-selling epics amortize)
    #[arg(long, default_value_t = 28)]
    days: u32,
    /// Runs/day for the detailed quantile table
    #[arg(long, default_value_t = 3)]
    runs: u32,
    /// Thunderstrike-Horde share of Fresh-EU region demand
    #[arg(long, default_value_t = 0.25)]
    share: f64,
    #[arg(long, default_value_t = 0.80)]
    nether_rate: f64,
    #[arg(long, default_value_t = 0.6667)]
    keep_blue: f64,
    #[arg(long, default_value_t = 0.50)]
    keep_epic: f64,
    /// Disable enchanting (no shard income)
    #[arg(long)]
    no_shards: bool,
    /// Raw gold + vendor trash + cloth per run, in gold
    #[arg(long, default_value_t = 25.0)]
    flat_gold: f64,
    /// Repair bill per run, in gold
    #[arg(long, default_value_t = 6.0)]
    repairs: f64,
    /// Craft-ahead multiplier on daily demand
    #[arg(long, default_value_t = 2.0)]
    headroom: f64,
    /// Badges per nether at G'eras (0 = vendor not available this phase, the
    /// current SSC/TK situation - badges then only buy gear, not nethers)
    #[arg(long, default_value_t = 0)]
    badges_per_nether: u32,
    #[arg(long, default_value_t = 42)]
    seed: u64,
    /// WoW AddOns directory
    #[arg(long)]
    addons: Option<PathBuf>,
    /// nether_recipes.json produced by primal-nether-analysis/extract_recipes.lua
    #[arg(long)]
    recipes: Option<PathBuf>,
    /// Curated heroic dungeon list
    #[arg(long)]
    dungeons: Option<PathBuf>,
    /// Comma-separated item names: restrict crafting to these (case-insensitive)
    #[arg(long)]
    only: Option<String>,
}

fn gold(copper: f64) -> String {
    format!("{:.0}g", copper / 10_000.0)
}

fn main() -> Result<()> {
    let args = Args::parse();
    let home = std::env::var("HOME").context("HOME not set")?;
    let addons = args.addons.clone().unwrap_or_else(|| {
        PathBuf::from(&home).join(
            "Games/battlenet/drive_c/Program Files (x86)/World of Warcraft/_anniversary_/Interface/AddOns",
        )
    });
    let recipes_path = args.recipes.clone().unwrap_or_else(|| {
        PathBuf::from(&home).join("ccsandbox/wow/primal-nether-analysis/output/nether_recipes.json")
    });
    let dungeons_path = args.dungeons.clone().unwrap_or_else(|| {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("data/dungeons.json")
    });

    let market = data::Market {
        items: data::parse_appdata(&addons.join("TradeSkillMaster_AppHelper/AppData.lua"))?,
        vendor: data::parse_vendor(&addons.join("TradeSkillMaster/LibTSMData/Item/VendorSell.lua"))?,
    };
    let recipes: Vec<data::RawRecipe> =
        serde_json::from_str(&std::fs::read_to_string(&recipes_path).with_context(|| {
            format!(
                "reading {} (run extract_recipes.lua first)",
                recipes_path.display()
            )
        })?)?;
    let dungeons: Vec<data::Dungeon> =
        serde_json::from_str(&std::fs::read_to_string(&dungeons_path)?)?;

    let mut scenarios = data::build_crafts(&recipes, &market);
    if let Some(only) = &args.only {
        let wanted: Vec<String> = only.split(',').map(|s| s.trim().to_lowercase()).collect();
        for crafts in scenarios.values_mut() {
            crafts.retain(|c| wanted.iter().any(|w| c.name.to_lowercase() == *w));
        }
        scenarios.retain(|_, v| !v.is_empty());
    }
    scenarios.insert("(no sink)".into(), Vec::new());

    let shard_value = market.horde_mv(LARGE_PRISMATIC_SHARD).unwrap_or(0.0) * AH_KEEP;
    let epic_de_value = 1.5 * market.horde_mv(VOID_CRYSTAL).unwrap_or(0.0) * AH_KEEP;

    let mk_params = |runs: u32| sim::Params {
        days: args.days,
        runs_per_day: runs,
        share: args.share,
        nether_rate: args.nether_rate,
        keep_blue: args.keep_blue,
        keep_epic: args.keep_epic,
        shards: !args.no_shards,
        shard_value,
        epic_de_value,
        flat_gold: args.flat_gold * 10_000.0,
        repairs: args.repairs * 10_000.0,
        headroom: args.headroom,
        badges_per_nether: (args.badges_per_nether > 0).then_some(args.badges_per_nether),
        run_min: 15.0,
        run_mode: 35.0,
        run_max: 45.0,
        overhead_min: 2.0,
        overhead_max: 5.0,
    };

    let simulate = |crafts: &[Craft], runs: u32, scen_idx: u64| -> Vec<sim::IterResult> {
        let p = mk_params(runs);
        (0..args.iterations)
            .map(|i| {
                let seed = args
                    .seed
                    .wrapping_mul(0x9E3779B97F4A7C15)
                    .wrapping_add((scen_idx << 40) | ((runs as u64) << 32) | i as u64);
                sim::run_iteration(seed, &p, &dungeons, crafts)
            })
            .collect()
    };

    println!(
        "nether-sim: {} iterations x {} days | share {:.0}% | nether {:.0}% | keep blue {:.0}% / epic {:.0}% | shards {}",
        args.iterations,
        args.days,
        args.share * 100.0,
        args.nether_rate * 100.0,
        args.keep_blue * 100.0,
        args.keep_epic * 100.0,
        if args.no_shards { "off" } else { "on" }
    );

    // --- sweep: median gold/day for 1..=5 runs/day ---
    println!("\nMedian gold/day by runs/day:");
    println!("{:<16} {:>8} {:>8} {:>8} {:>8} {:>8}", "profession", 1, 2, 3, 4, 5);
    let mut medians: Vec<(String, Vec<f64>)> = Vec::new();
    for (idx, (name, crafts)) in scenarios.iter().enumerate() {
        let mut row = Vec::new();
        for runs in 1..=5u32 {
            let res = simulate(crafts, runs, idx as u64);
            let s = sim::summarize(&res, args.days, &[0.5]);
            row.push(s.quantiles[0]);
        }
        medians.push((name.clone(), row));
    }
    medians.sort_by(|a, b| b.1[2].total_cmp(&a.1[2]));
    for (name, row) in &medians {
        println!(
            "{:<16} {:>8} {:>8} {:>8} {:>8} {:>8}",
            name,
            gold(row[0]),
            gold(row[1]),
            gold(row[2]),
            gold(row[3]),
            gold(row[4])
        );
    }

    // --- detail at chosen runs/day ---
    println!(
        "\nDetail at {} runs/day (gold/day quantiles across {}-day horizons):",
        args.runs, args.days
    );
    println!(
        "{:<16} {:>8} {:>8} {:>8} {:>8} {:>8} {:>10}",
        "profession", "P10", "P25", "P50", "P75", "P90", "g/hr med"
    );
    for (name, _) in &medians {
        let crafts = &scenarios[name];
        let idx = scenarios.keys().position(|k| k == name).unwrap();
        let res = simulate(crafts, args.runs, idx as u64);
        let s = sim::summarize(&res, args.days, QUANTILES);
        println!(
            "{:<16} {:>8} {:>8} {:>8} {:>8} {:>8} {:>10}",
            name,
            gold(s.quantiles[0]),
            gold(s.quantiles[1]),
            gold(s.quantiles[2]),
            gold(s.quantiles[3]),
            gold(s.quantiles[4]),
            gold(s.gold_per_hour_median)
        );

        // craft mix
        let mut mix: Vec<(f64, &Craft)> = s
            .mean_sold_per_week
            .iter()
            .zip(crafts)
            .filter(|(m, _)| **m > 0.05)
            .map(|(m, c)| (*m, c))
            .collect();
        mix.sort_by(|a, b| {
            (b.0 * b.1.profit).total_cmp(&(a.0 * a.1.profit))
        });
        for (m, c) in mix.iter().take(4) {
            println!(
                "                  {:<38} {:>5.1}/wk sold, {:>6}/craft profit",
                c.name,
                m,
                gold(c.profit)
            );
        }
    }

    println!(
        "\nNotes: prices = Horde marketValue x0.95 snapshot; demand/item/day ~ Poisson({:.0}% x region sold/day);",
        args.share * 100.0
    );
    println!("unsold terminal inventory recovers mat cost only; banked nethers/badges expire worthless at horizon end (conservative).");
    Ok(())
}
