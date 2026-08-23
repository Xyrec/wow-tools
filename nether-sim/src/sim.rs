use crate::data::{Craft, Dungeon};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use rand_distr::{Binomial, Distribution, Poisson, Triangular};

pub struct Params {
    pub days: u32,
    pub runs_per_day: u32,
    pub share: f64,       // our faction-realm's share of region demand
    pub nether_rate: f64, // chance the nether drops and is ours
    pub keep_blue: f64,   // chance nobody needs a given boss blue
    pub keep_epic: f64,
    pub shards: bool,          // enchanting present
    pub shard_value: f64,      // copper, after AH cut
    pub epic_de_value: f64,    // copper, after AH cut (avg void crystals)
    pub flat_gold: f64,        // copper per run (loot gold, vendor trash, cloth)
    pub repairs: f64,          // copper per run
    pub headroom: f64,         // craft-ahead multiplier on daily demand
    /// Badges needed to buy a nether from G'eras; None until that vendor exists
    /// (not available in the current phase).
    pub badges_per_nether: Option<u32>,
    pub run_min: f64,
    pub run_mode: f64,
    pub run_max: f64,
    pub overhead_min: f64,
    pub overhead_max: f64,
}

pub struct IterResult {
    pub gold: f64,  // copper over the horizon
    pub hours: f64,
    pub sold: Vec<u32>,
}

pub fn run_iteration(
    seed: u64,
    p: &Params,
    dungeons: &[Dungeon],
    crafts: &[Craft],
) -> IterResult {
    let mut rng = StdRng::seed_from_u64(seed);
    let run_dur = Triangular::new(p.run_min, p.run_max, p.run_mode).unwrap();

    let mut gold = 0.0_f64;
    let mut hours = 0.0_f64;
    let mut nethers: u32 = 0;
    let mut badges: u32 = 0;
    let mut inv = vec![0u32; crafts.len()];
    let mut sold = vec![0u32; crafts.len()];

    for _day in 0..p.days {
        // --- tank heroics ---
        for _run in 0..p.runs_per_day {
            let d = &dungeons[rng.gen_range(0..dungeons.len())];
            hours += (run_dur.sample(&mut rng)
                + rng.gen_range(p.overhead_min..=p.overhead_max))
                / 60.0;
            badges += d.bosses;
            if rng.gen_bool(p.nether_rate) {
                nethers += 1;
            }
            if p.shards {
                let blues = (d.bosses + 1) as u64; // final boss drops an extra blue
                let kept = Binomial::new(blues, p.keep_blue).unwrap().sample(&mut rng);
                gold += kept as f64 * p.shard_value;
                if rng.gen_bool(p.keep_epic) {
                    gold += p.epic_de_value;
                }
            }
            gold += p.flat_gold - p.repairs;
        }
        if p.runs_per_day > 0 {
            badges += 2; // daily heroic quest
        }
        if let Some(cost) = p.badges_per_nether {
            while badges >= cost {
                badges -= cost;
                nethers += 1;
            }
        }

        // --- craft: best profit/nether first, bounded by sales headroom ---
        for (i, c) in crafts.iter().enumerate() {
            let cap = c.region_sold_per_day * p.share;
            if cap <= 0.0 {
                continue; // market never absorbs it - don't craft
            }
            // ceil: even slow items may keep one unit listed
            let room = ((cap * p.headroom).ceil() as i64 - inv[i] as i64).max(0) as u32;
            let n = room.min(nethers / c.nethers);
            if n > 0 {
                inv[i] += n;
                nethers -= n * c.nethers;
                gold -= n as f64 * c.mat_cost;
            }
        }

        // --- sell: daily demand is Poisson(realm share of region volume) ---
        for (i, c) in crafts.iter().enumerate() {
            let cap = c.region_sold_per_day * p.share;
            if cap <= 0.0 || inv[i] == 0 {
                continue;
            }
            let demand = Poisson::new(cap).unwrap().sample(&mut rng) as u32;
            let s = demand.min(inv[i]);
            inv[i] -= s;
            sold[i] += s;
            gold += s as f64 * c.unit_revenue;
        }
    }

    // Terminal: unsold inventory recovers mat cost only; banked nethers/badges
    // are worth nothing inside the horizon (conservative on both counts).
    for (i, c) in crafts.iter().enumerate() {
        gold += inv[i] as f64 * c.mat_cost;
    }

    IterResult { gold, hours, sold }
}

pub struct Summary {
    pub quantiles: Vec<f64>, // copper per day at requested quantiles
    pub gold_per_hour_median: f64,
    pub mean_sold_per_week: Vec<f64>,
}

pub fn summarize(results: &[IterResult], days: u32, quantiles: &[f64]) -> Summary {
    let mut golds: Vec<f64> = results.iter().map(|r| r.gold).collect();
    golds.sort_by(|a, b| a.total_cmp(b));
    let q = |p: f64| -> f64 {
        let idx = ((golds.len() - 1) as f64 * p).round() as usize;
        golds[idx] / days as f64
    };

    let mut gph: Vec<f64> = results
        .iter()
        .filter(|r| r.hours > 0.0)
        .map(|r| r.gold / r.hours)
        .collect();
    gph.sort_by(|a, b| a.total_cmp(b));
    let gph_median = if gph.is_empty() { 0.0 } else { gph[gph.len() / 2] };

    let n_items = results.first().map_or(0, |r| r.sold.len());
    let mut mean_sold = vec![0.0; n_items];
    for r in results {
        for (i, s) in r.sold.iter().enumerate() {
            mean_sold[i] += *s as f64;
        }
    }
    let weeks = results.len() as f64 * days as f64 / 7.0;
    for m in &mut mean_sold {
        *m /= weeks;
    }

    Summary {
        quantiles: quantiles.iter().map(|&p| q(p)).collect(),
        gold_per_hour_median: gph_median,
        mean_sold_per_week: mean_sold,
    }
}
