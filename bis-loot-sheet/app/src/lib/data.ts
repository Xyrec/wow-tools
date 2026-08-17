import { useEffect, useState } from "react"
import type { ItemFacts, SlotEntry, ZoneData } from "@/types"
import { CLASS_ORDER, ZONE_PHASES, specClass } from "./wow"

// Non-eager: each zone JSON becomes its own hashed chunk, fetched on demand.
// Cloudflare serves hashed assets immutably, so unchanged zones stay cached
// across deploys; only re-aggregated zones get new hashes.
const modules = import.meta.glob("../data/*.json") as Record<
  string,
  () => Promise<{ default: ZoneData }>
>

const tagOf = (path: string) => path.replace("../data/", "").replace(".json", "")

/** Zone tags present in the build, ordered by anniversary phase. */
export const zoneTags = Object.keys(modules)
  .map(tagOf)
  .sort((a, b) => (ZONE_PHASES[a] ?? 99) - (ZONE_PHASES[b] ?? 99))

const cache = new Map<string, ZoneData>()

export async function loadZone(tag: string): Promise<ZoneData> {
  const cached = cache.get(tag)
  if (cached) return cached
  const path = `../data/${tag}.json`
  const zone = (await modules[path]()).default
  cache.set(tag, zone)
  return zone
}

/** Load a zone's data; returns undefined while the chunk is in flight. */
export function useZone(tag: string | undefined): ZoneData | undefined {
  const [zone, setZone] = useState<ZoneData | undefined>(() =>
    tag ? cache.get(tag) : undefined,
  )
  useEffect(() => {
    if (!tag) return
    let stale = false
    const cached = cache.get(tag)
    if (cached) {
      setZone(cached)
      return
    }
    setZone(undefined)
    loadZone(tag).then((z) => {
      if (!stale) setZone(z)
    })
    return () => {
      stale = true
    }
  }, [tag])
  return zone
}

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
