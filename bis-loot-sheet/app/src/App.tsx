import { useEffect, useState } from "react"

declare global {
  interface Window {
    $WowheadPower?: { refreshLinks: () => void }
  }
}
import { Overview } from "@/components/Overview"
import { PairCard } from "@/components/PairCard"
import { SlotCard } from "@/components/SlotCard"
import { SpecSidebar } from "@/components/SpecSidebar"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { splitWeapons, useZone, zoneTags } from "@/lib/data"
import {
  CLASS_COLORS,
  SLOT_ORDER,
  ZONE_LABELS,
  ZONE_PHASES,
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
  // Default to the latest phase present in the build.
  const [zoneTag, setZoneTag] = useState(
    zoneTags.includes("phase-3") ? "phase-3" : zoneTags.at(-1),
  ) // default: the guild's current phase
  const zone = useZone(zoneTag)
  const [specKey, setSpecKey] = useState("")
  const spec = zone && specKey ? zone.specs[specKey] : undefined

  // Wowhead's tooltip script only scans on load; re-scan after re-renders.
  useEffect(() => {
    const id = setTimeout(() => window.$WowheadPower?.refreshLinks(), 50)
    return () => clearTimeout(id)
  }, [zoneTag, specKey, zone])

  if (zoneTags.length === 0)
    return <main className="p-8">No data generated yet — run the pipeline.</main>

  return (
    <div className="mx-auto max-w-7xl p-4">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">TBC Item Distribution — from Warcraft Logs</h1>
          <p className="max-w-2xl text-xs text-muted-foreground">
            An item distribution list built from Warcraft Logs: what the top ~2,000 ranked players
            of each spec actually wore, and how usage splits between items. The higher an
            item&apos;s equipped&nbsp;%, the more likely it is <em>the</em> BiS for that slot —
            curated BiS lists may differ.
          </p>
        </div>
        <Select
          items={zoneTags.map((tag) => ({
            label: `P${ZONE_PHASES[tag] ?? "?"} · ${ZONE_LABELS[tag] ?? tag}`,
            value: tag,
          }))}
          value={zoneTag}
          onValueChange={(v) => v && setZoneTag(v)}
        >
          <SelectTrigger className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {zoneTags.map((tag) => (
                <SelectItem key={tag} value={tag}>
                  P{ZONE_PHASES[tag] ?? "?"} · {ZONE_LABELS[tag] ?? tag}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </header>

      {!zone ? (
        <p className="p-8 text-sm text-muted-foreground">Loading zone data…</p>
      ) : (
        <div className="flex items-start gap-4">
          {/* Sticky sidebar with its own scrollbar; the item list scrolls with the page. */}
          <div className="sticky top-0 max-h-dvh w-48 shrink-0 overflow-y-auto overscroll-contain py-4 pr-2">
            <SpecSidebar zone={zone} selected={specKey} onSelect={setSpecKey} />
          </div>

          <main className="min-w-0 flex-1">
            {specKey === "" ? (
              <Overview key={zone.zone} zone={zone} />
            ) : spec ? (
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
                {ROLE_CAVEATS[specRole(specKey)] && (
                  <p className="mb-4 rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-200">
                    {ROLE_CAVEATS[specRole(specKey)]}
                  </p>
                )}
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  {(() => {
                    const slots = splitWeapons(spec.slots, zone.items)
                    // Pair-distribution cards follow their singles category.
                    const pairAfter: Record<string, [string, string]> = {
                      ring: ["ring", "Ring Combinations"],
                      trinket: ["trinket", "Trinket Combinations"],
                      off_hand: ["weapon", "Weapon Combinations"],
                    }
                    return SLOT_ORDER.flatMap(([slot, label]) => {
                      // 2H/MH cards derive from the shared main-hand pool.
                      const nSlot =
                        slot === "two_hand" || slot === "main_hand" ? "main_hand" : slot
                      const cards = [
                        <SlotCard
                          key={slot}
                          slot={slot}
                          label={label}
                          entries={slots[slot] ?? []}
                          items={zone.items}
                          n={spec.slotN?.[nSlot]}
                        />,
                      ]
                      const pair = pairAfter[slot]
                      if (pair && spec.pairs?.[pair[0]]?.length) {
                        cards.push(
                          <PairCard
                            key={`pair-${pair[0]}`}
                            label={pair[1]}
                            entries={spec.pairs[pair[0]]}
                            items={zone.items}
                            n={spec.pairN?.[pair[0]]}
                          />,
                        )
                      }
                      return cards
                    })
                  })()}
                </div>
              </>
            ) : (
              <p className="text-muted-foreground">No data for this spec in this zone.</p>
            )}
          </main>
        </div>
      )}
    </div>
  )
}
