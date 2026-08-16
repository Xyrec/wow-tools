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
  karazhan: 1,
  "gruul-magtheridon": 1,
  "ssc-tk": 2,
  "bt-hyjal": 3,
  "zul-aman": 4,
  sunwell: 5,
}

export const ZONE_LABELS: Record<string, string> = {
  karazhan: "Karazhan",
  "gruul-magtheridon": "Gruul / Magtheridon",
  "ssc-tk": "SSC / TK",
  "bt-hyjal": "Hyjal / Black Temple",
  "zul-aman": "Zul'Aman",
  sunwell: "Sunwell Plateau",
}

/** Display floor from docs/PLAN.md: usage under 2% is considered noise. */
export const DISPLAY_FLOOR_PCT = 2.0
