import { useMemo, useState } from "react"
import { SlotCard } from "@/components/SlotCard"
import { SpecSidebar } from "@/components/SpecSidebar"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { zones } from "@/lib/data"
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
  const [zoneTag, setZoneTag] = useState(zones[0]?.zone)
  const zone = useMemo(() => zones.find((z) => z.zone === zoneTag) ?? zones[0], [zoneTag])
  const [specKey, setSpecKey] = useState("Shaman-Enhancement")
  const spec = zone?.specs[specKey]
  const role = specRole(specKey)

  if (!zone) return <main className="p-8">No data generated yet — run the pipeline.</main>

  return (
    <div className="mx-auto flex h-screen max-w-7xl flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">TBC BiS — from Warcraft Logs</h1>
          <p className="text-xs text-muted-foreground">
            What top parsers actually wore, per phase-pure partition ({zone.regions.join("+")},
            top {zone.maxPages * 100}/region/spec/boss{zone.maxPages < 20 ? " — basic data set" : ""})
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

      <div className="flex min-h-0 flex-1 gap-4">
        <SpecSidebar zone={zone} selected={specKey} onSelect={setSpecKey} />

        <main className="min-w-0 flex-1 overflow-y-auto">
          {spec ? (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <h2
                  className="text-lg font-bold"
                  style={{ color: CLASS_COLORS[specClass(specKey)] }}
                >
                  {specName(specKey)} {specClass(specKey)}
                </h2>
                <Badge variant="secondary">
                  {spec.sampleSize.toLocaleString()} parses sampled
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
                {SLOT_ORDER.map(([slot, label]) => (
                  <SlotCard
                    key={slot}
                    label={label}
                    entries={spec.slots[slot] ?? []}
                    items={zone.items}
                  />
                ))}
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
