#![allow(dead_code)]

mod check;
mod common;
mod find_stat;
mod lookup;
mod parse;
mod scrape;

use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "wow-tools", about = "TBC BiS gear checker and item tools")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Compare equipped gear against BiS lists
    Check {
        /// Spec slug (e.g. resto-shaman, prot-warrior, fury-warrior)
        #[arg(long)]
        spec: String,
        /// Character data file (default: auto from spec)
        file: Option<String>,
        /// Show crafted items in upgrades
        #[arg(long)]
        show_crafted: bool,
        /// Include old phases (phase-0) as fallback data
        #[arg(long)]
        include_old_phases: bool,
    },
    /// Regenerate bis_gear.json from source HTML
    Parse {
        /// Spec slug (e.g. resto-shaman, prot-warrior)
        #[arg(long)]
        spec: String,
        /// Parser to use (wowtbc, icy-veins, atlasloot, all). Default: all
        #[arg(long, default_value = "all")]
        parser: String,
        /// Override output JSON path
        #[arg(long)]
        output: Option<String>,
    },
    /// Look up TBC item stats from cmangos DB
    Lookup {
        /// Item IDs to look up
        item_ids: Vec<u32>,
        /// Show side-by-side comparison with diff column
        #[arg(long)]
        compare: bool,
    },
    /// Scrape BiS data from wowtbc.gg for all specs
    Scrape {
        /// Spec filter (e.g. "shaman", "holy-paladin"). Omit for all specs.
        spec: Option<String>,
    },
    /// Find gear upgrades for a specific stat target
    FindStat {
        /// Character data file
        file: String,
        /// Stat to optimize (defense, dodge, parry, block, hit, crit, haste, expertise, resilience)
        #[arg(long)]
        stat: String,
        /// Target value for the stat
        #[arg(long)]
        target: f64,
        /// Source filter (easy, dungeon, boe, rep, all)
        #[arg(long, default_value = "easy")]
        source: String,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Check {
            spec,
            file,
            show_crafted,
            include_old_phases,
        } => {
            check::run(&spec, file.as_deref(), show_crafted, include_old_phases)?;
        }
        Commands::Parse {
            spec,
            parser,
            output,
        } => {
            let resolved = common::resolve_spec(&spec)?;
            let out = output.as_deref();
            match parser.as_str() {
                "wowtbc" | "wtbc" => parse::wowtbc::run(resolved, out)?,
                "icy-veins" | "iv" => parse::icy_veins::run(resolved, out)?,
                "atlasloot" | "al" => parse::atlasloot::run(resolved, out)?,
                "all" => {
                    parse::wowtbc::run(resolved, None)?;
                    parse::icy_veins::run(resolved, None)?;
                    parse::atlasloot::run(resolved, None)?;
                }
                other => anyhow::bail!(
                    "Unknown parser '{other}'. Use: wowtbc, icy-veins, atlasloot, all."
                ),
            }
        }
        Commands::Lookup { item_ids, compare } => {
            lookup::run(&item_ids, compare)?;
        }
        Commands::Scrape { spec } => {
            scrape::run(spec.as_deref())?;
        }
        Commands::FindStat {
            file,
            stat,
            target,
            source,
        } => {
            find_stat::run(&file, &stat, target, &source)?;
        }
    }

    Ok(())
}
