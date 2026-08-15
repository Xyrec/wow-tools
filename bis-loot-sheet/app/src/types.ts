export interface ItemFacts {
  name: string
  quality: number
  itemLevel: number
  slot: string
  unique: boolean
  uniqueEquipped: boolean
  icon?: string
  wclName?: string
  armorType?: string
  allowableClasses?: string[]
  setId?: number
  token?: boolean
  dropOnly?: boolean
  sources?: number[]
  laterPhase?: string
}

export interface SlotEntry {
  id: number
  count: number
  pct: number
}

export interface SpecData {
  sampleSize: number
  slots: Record<string, SlotEntry[]>
}

export interface ZoneData {
  zone: string
  zoneId: number
  partition: number
  anniversaryPhase: number
  regions: string[]
  maxPages: number
  generatedAt: string
  encounters: Record<string, string>
  items: Record<string, ItemFacts>
  specs: Record<string, SpecData>
}
