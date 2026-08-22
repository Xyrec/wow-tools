export const CLASS_COLORS: Record<string, string> = {
  Druid: "#FF7C0A",
  Hunter: "#AAD372",
  Mage: "#3FC7EB",
  Paladin: "#F48CBA",
  Priest: "#FFFFFF",
  Rogue: "#FFF468",
  Shaman: "#0070DD",
  Warlock: "#8788EE",
  Warrior: "#C69B6D",
}

export const CLASS_ORDER = [
  "Druid",
  "Hunter",
  "Mage",
  "Paladin",
  "Priest",
  "Rogue",
  "Shaman",
  "Warlock",
  "Warrior",
]

export const QUALITY_COLORS: Record<number, string> = {
  0: "#9d9d9d",
  1: "#ffffff",
  2: "#1eff00",
  3: "#0070dd",
  4: "#a335ee",
  5: "#ff8000",
}

/** Display order + labels for the aggregated slot keys. */
export const SLOT_ORDER: [string, string][] = [
  ["head", "Head"],
  ["neck", "Neck"],
  ["shoulder", "Shoulders"],
  ["back", "Back"],
  ["chest", "Chest"],
  ["wrist", "Wrists"],
  ["hands", "Hands"],
  ["waist", "Waist"],
  ["legs", "Legs"],
  ["feet", "Feet"],
  ["ring", "Rings"],
  ["trinket", "Trinkets"],
  ["two_hand", "Two Hand"],
  ["main_hand", "Main Hand"],
  ["off_hand", "Off Hand"],
  ["ranged", "Ranged / Relic"],
]

/** Percentage-point window below the top item within which items co-rank as BiS. */
export const BIS_TIE_WINDOW = 5.0

const HEALER_SPECS = new Set(["Restoration", "Holy", "Discipline"])
const TANK_SPECS = new Set(["Warrior-Protection", "Paladin-Protection", "Druid-Guardian"])

export type Role = "dps" | "healer" | "tank"

export function specRole(specKey: string): Role {
  const spec = specKey.split("-").slice(1).join("-")
  if (HEALER_SPECS.has(spec)) return "healer"
  if (TANK_SPECS.has(specKey)) return "tank"
  return "dps"
}

export function specClass(specKey: string): string {
  return specKey.split("-")[0]
}

export function specName(specKey: string): string {
  return specKey.split("-").slice(1).join("-")
}

export function iconUrl(icon: string | undefined): string | undefined {
  if (!icon) return undefined
  return `https://wow.zamimg.com/images/wow/icons/large/${icon.replace(/\.jpg$/, "")}.jpg`
}

export function wowheadUrl(itemId: number): string {
  return `https://www.wowhead.com/tbc/item=${itemId}`
}

export const ZONE_PHASES: Record<string, number> = {
  "phase-1": 1,
  "phase-2": 2,
  "phase-3": 3,
  "phase-4": 4,
  "phase-5": 5,
}

/** Short, unambiguous spec names for prio chains and CSV export. */
export const SPEC_SHORT: Record<string, string> = {
  "Druid-Balance": "Balance",
  "Druid-Feral": "Feral DPS",
  "Druid-Guardian": "Feral Tank",
  "Druid-Restoration": "Resto Druid",
  "Hunter-Beast Mastery": "BM Hunter",
  "Hunter-Marksmanship": "MM Hunter",
  "Hunter-Survival": "Survival",
  "Mage-Arcane": "Arcane Mage",
  "Mage-Fire": "Fire Mage",
  "Mage-Frost": "Frost Mage",
  "Paladin-Holy": "Holy Paladin",
  "Paladin-Protection": "Prot Paladin",
  "Paladin-Retribution": "Retribution",
  "Priest-Discipline": "Disc Priest",
  "Priest-Holy": "Holy Priest",
  "Priest-Shadow": "Shadow Priest",
  "Rogue-Assassination": "Assa Rogue",
  "Rogue-Combat": "Combat Rogue",
  "Rogue-Subtlety": "Sub Rogue",
  "Shaman-Elemental": "Elemental",
  "Shaman-Enhancement": "Enhancement",
  "Shaman-Restoration": "Resto Shaman",
  "Warlock-Affliction": "Affli Lock",
  "Warlock-Demonology": "Demo Lock",
  "Warlock-Destruction": "Destro Lock",
  "Warrior-Arms": "Arms",
  "Warrior-Fury": "Fury",
  "Warrior-Protection": "Prot Warrior",
}

// Trash pseudo-encounters: 900000 + raid map id (see pipeline lootmap.py).
const TRASH_RAIDS: Record<number, string> = {
  900532: "Karazhan",
  900534: "Hyjal Summit",
  900544: "Magtheridon's Lair",
  900548: "Serpentshrine Cavern",
  900550: "Tempest Keep",
  900564: "Black Temple",
  900565: "Gruul's Lair",
  900568: "Zul'Aman",
  900580: "Sunwell Plateau",
}

/** Raid instance per WCL encounter id, for grouping multi-raid zones. */
export function raidOfEncounter(encounterId: number): string {
  if (encounterId in TRASH_RAIDS) return TRASH_RAIDS[encounterId]
  if (encounterId >= 601 && encounterId <= 609) return "Black Temple"
  if (encounterId >= 618 && encounterId <= 622) return "Hyjal Summit"
  if (encounterId >= 623 && encounterId <= 628) return "Serpentshrine Cavern"
  if (encounterId >= 730 && encounterId <= 733) return "Tempest Keep"
  if (encounterId >= 649 && encounterId <= 650) return "Gruul's Lair"
  if (encounterId === 651) return "Magtheridon's Lair"
  if (encounterId >= 652 && encounterId <= 662) return "Karazhan"
  if (encounterId >= 1189 && encounterId <= 1194) return "Zul'Aman"
  if (encounterId >= 724 && encounterId <= 729) return "Sunwell Plateau"
  return "Other"
}

export const ZONE_LABELS: Record<string, string> = {
  "phase-1": "Kara · Gruul · Mag",
  "phase-2": "SSC / TK",
  "phase-3": "Hyjal / Black Temple",
  "phase-4": "Zul'Aman",
  "phase-5": "Sunwell Plateau",
}

/** Display floor from docs/PLAN.md: usage under 2% is considered noise. */
export const DISPLAY_FLOOR_PCT = 2.0
