import type { ItemFacts, SlotEntry, ZoneData } from "@/types"
import { CLASS_ORDER, specClass } from "./wow"

const modules = import.meta.glob("../data/*.json", { eager: true }) as Record<
  string,
  { default: ZoneData }
>

export const zones: ZoneData[] = Object.values(modules)
  .map((m) => m.default)
  .sort((a, b) => a.anniversaryPhase - b.anniversaryPhase)

/**
 * WCL's gear array puts two-handers in the main-hand slot, which reads as
 * "equip this 2H plus an off hand". Split them into their own display slot.
 */
export function splitWeapons(
  slots: Record<string, SlotEntry[]>,
  items: Record<string, ItemFacts>,
): Record<string, SlotEntry[]> {
  const mainHand = slots["main_hand"] ?? []
  return {
    ...slots,
    two_hand: mainHand.filter((e) => items[e.id]?.slot === "two_hand"),
    main_hand: mainHand.filter((e) => items[e.id]?.slot !== "two_hand"),
  }
}

export function specKeysByClass(zone: ZoneData): Map<string, string[]> {
  const byClass = new Map<string, string[]>()
  for (const cls of CLASS_ORDER) byClass.set(cls, [])
  for (const key of Object.keys(zone.specs).sort()) {
    byClass.get(specClass(key))?.push(key)
  }
  for (const [cls, keys] of byClass) if (keys.length === 0) byClass.delete(cls)
  return byClass
}
