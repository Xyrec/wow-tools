import type { ItemFacts, ZoneData } from "@/types"

/** Loot-priority model (see docs/PLAN.md; v1 grilled 2026-08-21, phase
 *  multiplier added on user decision 2026-08-23):
 *  score(spec) = Σ over current..P5 of [usage + max(0, usage − best_alt)] · mult^(phase − current)
 *  membership: floor, cap, 50% break; "=" within 8%. */

export const PRIO_FLOOR = 10
export const PRIO_CAP = 4
export const PRIO_BREAK_RATIO = 0.5
export const PRIO_TIE_REL = 0.08
/** Future-phase weight: each phase past the current one multiplies that
 *  phase's need by this factor (P3 sheet: P3 ×1, P4 ×1.5, P5 ×2.25) —
 *  items that stay useful in future phases are the sheet's whole point. */
export const PRIO_PHASE_MULT = 1.5
/** Specs sampled below this fraction of the phase's median sample size are
 *  excluded from that phase — too few players for the distribution to mean
 *  anything (P3: MM Hunter, Frost, Assa, Sub, Demo all fall under 1/3). */
export const PRIO_MIN_SAMPLE_RATIO = 1 / 3

const sampledCache = new WeakMap<ZoneData, Set<string>>()

/** Specs with a large enough sample in this zone to be scored. */
export function wellSampled(zone: ZoneData): Set<string> {
  let set = sampledCache.get(zone)
  if (!set) {
    const sizes = Object.values(zone.specs)
      .map((sd) => sd.sampleSize)
      .sort((a, b) => a - b)
    const median = sizes[Math.floor(sizes.length / 2)] ?? 0
    set = new Set(
      Object.entries(zone.specs)
        .filter(([, sd]) => sd.sampleSize >= PRIO_MIN_SAMPLE_RATIO * median)
        .map(([k]) => k),
    )
    sampledCache.set(zone, set)
  }
  return set
}

const PAIR_SLOTS = new Set(["ring", "trinket"])

export interface PhaseNeed {
  phase: number
  slot: string
  usage: number
  alt: number
  altId: number | null
  need: number
  /** Future-phase multiplier applied to `need` in the score sum. */
  weight: number
}

export interface SpecScore {
  spec: string
  score: number
  currentNeed: number
  needs: PhaseNeed[]
  /** For tokens: the piece this spec's score came from. */
  viaItem: number
}

function needIn(
  zone: ZoneData,
  spec: string,
  itemId: number,
  currentPhase: number,
): PhaseNeed | null {
  const sd = zone.specs[spec]
  if (!sd || !wellSampled(zone).has(spec)) return null
  for (const [slot, entries] of Object.entries(sd.slots)) {
    const mine = entries.find((e) => e.id === itemId)
    if (!mine) continue
    const others = entries.filter((e) => e.id !== itemId).sort((a, b) => b.pct - a.pct)
    // Two of these are worn: the true alternative is the item that would
    // replace this one, i.e. the 2nd-strongest other.
    const k = PAIR_SLOTS.has(slot) ? 1 : 0
    const alt = others[k]?.pct ?? 0
    return {
      phase: zone.anniversaryPhase,
      slot,
      usage: mine.pct,
      alt,
      altId: others[k]?.id ?? null,
      need: mine.pct + Math.max(0, mine.pct - alt),
      weight: PRIO_PHASE_MULT ** (zone.anniversaryPhase - currentPhase),
    }
  }
  return null
}

/** Score every spec for one droppable item across current..P5 zones.
 *  Tokens are scored via their redeemable pieces (max-scoring piece per spec). */
export function scoreItem(
  itemId: number,
  zones: ZoneData[],
  items: Record<string, ItemFacts>,
): SpecScore[] {
  const facts = items[itemId]
  const candidates = facts?.redeems?.length ? facts.redeems : [itemId]
  // A spec must be adequately sampled in the sheet's own phase to be named
  // at all; per-phase gating in needIn drops its under-sampled future terms.
  const specs = Object.keys(zones[0]?.specs ?? {}).filter((s) =>
    zones[0] ? wellSampled(zones[0]).has(s) : true,
  )
  const out: SpecScore[] = []
  for (const spec of specs) {
    let best: SpecScore | null = null
    for (const cand of candidates) {
      const currentPhase = zones[0]?.anniversaryPhase ?? 0
      const needs = zones
        .map((z) => needIn(z, spec, cand, currentPhase))
        .filter((n): n is PhaseNeed => n !== null)
      const score = needs.reduce((acc, n) => acc + n.need * n.weight, 0)
      if (!best || score > best.score) {
        best = {
          spec,
          score,
          currentNeed: needs.find((n) => n.phase === zones[0]?.anniversaryPhase)?.need ?? 0,
          needs,
          viaItem: cand,
        }
      }
    }
    if (best && best.score > 0) out.push(best)
  }
  // Deterministic: score desc, then current-phase need desc, then name.
  out.sort(
    (a, b) => b.score - a.score || b.currentNeed - a.currentNeed || a.spec.localeCompare(b.spec),
  )
  return out
}

export interface Chain {
  /** Named specs with equality-group markers: sep[i] joins named[i-1]→named[i]. */
  named: SpecScore[]
  seps: (">" | "=")[]
  tail: string
}

export function buildChain(scores: SpecScore[], isToken: boolean): Chain {
  const named: SpecScore[] = []
  for (const s of scores) {
    if (s.score < PRIO_FLOOR) break
    if (named.length >= PRIO_CAP) break
    // "Mishmash break": a big drop ends the named chain so no member of a
    // cluster of comparable low scores randomly wins third place.
    if (named.length > 0 && s.score < PRIO_BREAK_RATIO * named[named.length - 1].score) break
    named.push(s)
  }
  const seps: (">" | "=")[] = []
  for (let i = 1; i < named.length; i++) {
    const rel = (named[i - 1].score - named[i].score) / named[i - 1].score
    seps.push(rel <= PRIO_TIE_REL ? "=" : ">")
  }
  return { named, seps, tail: isToken ? "BiS > Non BiS" : "MS > OS" }
}
