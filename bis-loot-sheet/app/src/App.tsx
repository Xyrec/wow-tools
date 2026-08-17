import { useEffect, useMemo, useState } from "react"

declare global {
  interface Window {
    $WowheadPower?: { refreshLinks: () => void }
  }
}
import { Overview } from "@/components/Overview"
import { SlotCard } from "@/components/SlotCard"
import { SpecSidebar } from "@/components/SpecSidebar"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { splitWeapons, zones } from "@/lib/data"
import {
  CLASS_COLORS,
  SLOT_ORDER,
  ZONE_LABELS,
  specClass,
  specName,
  specRole,
} from "@/lib/wow"

const ROLE_CAVEATS: Record<string, string> = {
  healer:
    "Healer rankings are HPS-based. This shows what maximizes healing output on logs, not necessarily what a loot council should value (mana, utility, assignments).",
  tank: "Tank rankings are damage-based. This shows what top-parsing (DPS-focused) tanks wear, not necessarily the mitigation/stamina gear your guild wants tanks in.",
}

export default function App() {
  const [zoneTag, setZoneTag] = useState(zones.at(-1)?.zone) // default: latest phase
  const zone = useMemo(() => zones.find((z) => z.zone === zoneTag) ?? zones[0], [zoneTag])
  const [specKey, setSpecKey] = useState("")
  // Only the top2000 band (region windows, top ~2000/region) is complete and
  // exposed; the other bands remain in the data for future use.
  const spec = specKey ? zone?.specs[specKey] : undefined
  const bandData = spec?.bands.top2000
  const role = specRole(specKey)

  // Wowhead's tooltip script only scans on load; re-scan after re-renders.
  useEffect(() => {
    const id = setTimeout(() => window.$WowheadPower?.refreshLinks(), 50)
    return () => clearTimeout(id)
  }, [zoneTag, specKey])

  if (!zone) return <main className="p-8">No data generated yet — run the pipeline.</main>

  return (
    <div className="mx-auto max-w-7xl p-4">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">TBC BiS — from Warcraft Logs</h1>
          <p className="max-w-2xl text-xs text-muted-foreground">
            An item distribution list built from Warcraft Logs: what the top ~2,000 ranked players
            of each spec actually wore, and how usage splits between items. The higher an
            item&apos;s equipped&nbsp;%, the more likely it is <em>the</em> BiS for that slot —
            curated BiS lists may differ.
          </p>
        </div>
        <Tabs value={zone.zone} onValueChange={setZoneTag}>
          <TabsList>
            {zones.map((z) => (
              <TabsTrigger key={z.zone} value={z.zone}>
                P{z.anniversaryPhase} · {ZONE_LABELS[z.zone] ?? z.zone}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </header>

      <div className="flex items-start gap-4">
        {/* Sticky sidebar with its own scrollbar; the item list scrolls with the page. */}
        <div className="sticky top-0 max-h-dvh w-48 shrink-0 overflow-y-auto overscroll-contain py-4 pr-2">
          <SpecSidebar zone={zone} selected={specKey} onSelect={setSpecKey} />
        </div>

        <main className="min-w-0 flex-1">
          {specKey === "" ? (
            <Overview zone={zone} />
          ) : spec && bandData ? (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <h2
                  className="text-lg font-bold"
                  style={{ color: CLASS_COLORS[specClass(specKey)] }}
                >
                  {specName(specKey)} {specClass(specKey)}
                </h2>
                <Badge variant="secondary">
                  {bandData.sampleSize.toLocaleString()} parses sampled
                </Badge>
                <span className="text-xs text-muted-foreground">
                  generated {new Date(zone.generatedAt).toLocaleString()}
                </span>
              </div>
              {ROLE_CAVEATS[role] && (
                <p className="mb-4 rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-200">
                  {ROLE_CAVEATS[role]}
                </p>
              )}
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {(() => {
                  const slots = splitWeapons(bandData.slots, zone.items)
                  return SLOT_ORDER.map(([slot, label]) => (
                    <SlotCard
                      key={slot}
                      slot={slot}
                      label={label}
                      entries={slots[slot] ?? []}
                      items={zone.items}
                    />
                  ))
                })()}
              </div>
            </>
          ) : (
            <p className="text-muted-foreground">No data for this spec in this zone.</p>
          )}
        </main>
      </div>
    </div>
  )
}
