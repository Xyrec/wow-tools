import type { ZoneData } from "@/types"
import { CLASS_ORDER, specClass } from "./wow"

const modules = import.meta.glob("../data/*.json", { eager: true }) as Record<
  string,
  { default: ZoneData }
>

export const zones: ZoneData[] = Object.values(modules)
  .map((m) => m.default)
  .sort((a, b) => a.anniversaryPhase - b.anniversaryPhase)

export function specKeysByClass(zone: ZoneData): Map<string, string[]> {
  const byClass = new Map<string, string[]>()
  for (const cls of CLASS_ORDER) byClass.set(cls, [])
  for (const key of Object.keys(zone.specs).sort()) {
    byClass.get(specClass(key))?.push(key)
  }
  for (const [cls, keys] of byClass) if (keys.length === 0) byClass.delete(cls)
  return byClass
}
