use anyhow::{Result, bail};

pub struct SpecInfo {
    pub slug: &'static str,
    pub wowtbc_slug: &'static str,
    pub class: &'static str,
    pub armor_type: &'static str,
    pub aliases: &'static [&'static str],
}

pub static ALL_SPECS: &[SpecInfo] = &[
    // Shaman
    SpecInfo {
        slug: "resto-shaman",
        wowtbc_slug: "restoration-shaman",
        class: "Shaman",
        armor_type: "Mail",
        aliases: &["resto-shaman"],
    },
    SpecInfo {
        slug: "elemental-shaman",
        wowtbc_slug: "elemental-shaman",
        class: "Shaman",
        armor_type: "Mail",
        aliases: &["elemental-shaman", "ele-shaman"],
    },
    SpecInfo {
        slug: "enhancement-shaman",
        wowtbc_slug: "enhancement-shaman",
        class: "Shaman",
        armor_type: "Mail",
        aliases: &["enhancement-shaman", "enh-shaman"],
    },
    // Paladin
    SpecInfo {
        slug: "holy-paladin",
        wowtbc_slug: "holy-paladin",
        class: "Paladin",
        armor_type: "Plate",
        aliases: &["holy-paladin"],
    },
    SpecInfo {
        slug: "prot-paladin",
        wowtbc_slug: "protection-paladin",
        class: "Paladin",
        armor_type: "Plate",
        aliases: &["prot-paladin"],
    },
    SpecInfo {
        slug: "ret-paladin",
        wowtbc_slug: "retribution-paladin",
        class: "Paladin",
        armor_type: "Plate",
        aliases: &["ret-paladin"],
    },
    // Priest
    SpecInfo {
        slug: "holy-priest",
        wowtbc_slug: "holy-priest",
        class: "Priest",
        armor_type: "Cloth",
        aliases: &["holy-priest"],
    },
    SpecInfo {
        slug: "shadow-priest",
        wowtbc_slug: "shadow-priest",
        class: "Priest",
        armor_type: "Cloth",
        aliases: &["shadow-priest"],
    },
    // Druid
    SpecInfo {
        slug: "balance-druid",
        wowtbc_slug: "balance-druid",
        class: "Druid",
        armor_type: "Leather",
        aliases: &["balance-druid", "boomkin", "boomy-druid"],
    },
    SpecInfo {
        slug: "feral-tank-druid",
        wowtbc_slug: "feral-tank-druid",
        class: "Druid",
        armor_type: "Leather",
        aliases: &["feral-tank-druid", "bear-druid"],
    },
    SpecInfo {
        slug: "feral-dps-druid",
        wowtbc_slug: "feral-dps-druid",
        class: "Druid",
        armor_type: "Leather",
        aliases: &["feral-dps-druid", "cat-druid"],
    },
    SpecInfo {
        slug: "resto-druid",
        wowtbc_slug: "restoration-druid",
        class: "Druid",
        armor_type: "Leather",
        aliases: &["resto-druid"],
    },
    // Warrior
    SpecInfo {
        slug: "arms-warrior",
        wowtbc_slug: "arms-warrior",
        class: "Warrior",
        armor_type: "Plate",
        aliases: &["arms-warrior"],
    },
    SpecInfo {
        slug: "fury-warrior",
        wowtbc_slug: "fury-warrior",
        class: "Warrior",
        armor_type: "Plate",
        aliases: &["fury-warrior"],
    },
    SpecInfo {
        slug: "prot-warrior",
        wowtbc_slug: "protection-warrior",
        class: "Warrior",
        armor_type: "Plate",
        aliases: &["prot-warrior"],
    },
    // Hunter
    SpecInfo {
        slug: "bm-hunter",
        wowtbc_slug: "beast-mastery-hunter",
        class: "Hunter",
        armor_type: "Mail",
        aliases: &["bm-hunter", "beast-mastery-hunter"],
    },
    SpecInfo {
        slug: "marks-hunter",
        wowtbc_slug: "marksmanship-hunter",
        class: "Hunter",
        armor_type: "Mail",
        aliases: &["marks-hunter", "marksmanship-hunter", "mm-hunter"],
    },
    SpecInfo {
        slug: "survival-hunter",
        wowtbc_slug: "survival-hunter",
        class: "Hunter",
        armor_type: "Mail",
        aliases: &["survival-hunter", "sv-hunter"],
    },
    // Rogue
    SpecInfo {
        slug: "assassination-rogue",
        wowtbc_slug: "assassination-rogue",
        class: "Rogue",
        armor_type: "Leather",
        aliases: &["assassination-rogue", "assa-rogue", "mut-rogue"],
    },
    SpecInfo {
        slug: "combat-rogue",
        wowtbc_slug: "combat-rogue",
        class: "Rogue",
        armor_type: "Leather",
        aliases: &["combat-rogue"],
    },
    SpecInfo {
        slug: "subtlety-rogue",
        wowtbc_slug: "subtlety-rogue",
        class: "Rogue",
        armor_type: "Leather",
        aliases: &["subtlety-rogue", "sub-rogue"],
    },
    // Mage
    SpecInfo {
        slug: "arcane-mage",
        wowtbc_slug: "arcane-mage",
        class: "Mage",
        armor_type: "Cloth",
        aliases: &["arcane-mage"],
    },
    SpecInfo {
        slug: "fire-mage",
        wowtbc_slug: "fire-mage",
        class: "Mage",
        armor_type: "Cloth",
        aliases: &["fire-mage"],
    },
    SpecInfo {
        slug: "frost-mage",
        wowtbc_slug: "frost-mage",
        class: "Mage",
        armor_type: "Cloth",
        aliases: &["frost-mage"],
    },
    // Warlock
    SpecInfo {
        slug: "affliction-warlock",
        wowtbc_slug: "affliction-warlock",
        class: "Warlock",
        armor_type: "Cloth",
        aliases: &["affliction-warlock", "aff-warlock"],
    },
    SpecInfo {
        slug: "demo-warlock",
        wowtbc_slug: "demonology-warlock",
        class: "Warlock",
        armor_type: "Cloth",
        aliases: &["demo-warlock", "demonology-warlock"],
    },
    SpecInfo {
        slug: "destro-warlock",
        wowtbc_slug: "destruction-warlock",
        class: "Warlock",
        armor_type: "Cloth",
        aliases: &["destro-warlock", "destruction-warlock"],
    },
];

/// Find a spec by slug or alias. Suggests close matches on failure.
pub fn find_spec(input: &str) -> Result<&'static SpecInfo> {
    let input = input.trim().to_lowercase();

    // Exact match on slug
    if let Some(spec) = ALL_SPECS.iter().find(|s| s.slug == input) {
        return Ok(spec);
    }

    // Match on alias
    if let Some(spec) = ALL_SPECS
        .iter()
        .find(|s| s.aliases.iter().any(|a| *a == input))
    {
        return Ok(spec);
    }

    // Suggest close matches (specs containing the input as a substring)
    let suggestions: Vec<&str> = ALL_SPECS
        .iter()
        .filter(|s| {
            s.slug.contains(&input) || input.contains(s.slug.split('-').next().unwrap_or(""))
        })
        .map(|s| s.slug)
        .collect();

    if suggestions.is_empty() {
        bail!(
            "Unknown spec '{input}'. Available specs:\n  {}",
            ALL_SPECS
                .iter()
                .map(|s| s.slug)
                .collect::<Vec<_>>()
                .join(", ")
        );
    } else {
        bail!(
            "Unknown spec '{input}'. Did you mean: {}?",
            suggestions.join(", ")
        );
    }
}

pub fn all_specs() -> &'static [SpecInfo] {
    ALL_SPECS
}
