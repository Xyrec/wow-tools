import { useMemo, useState } from "react"
import { ChevronDown, ChevronRight, Download } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useZone } from "@/lib/data"
import { buildChain, scoreItem, wellSampled, type Chain, type SpecScore } from "@/lib/prio"
import {
  CLASS_COLORS,
  QUALITY_COLORS,
  SPEC_SHORT,
  iconUrl,
  raidOfEncounter,
  specClass,
  wowheadUrl,
} from "@/lib/wow"
import type { ItemFacts, ZoneData } from "@/types"

function ChainText({ chain }: { chain: Chain }) {
  if (chain.named.length === 0)
    return <span className="text-sm text-muted-foreground">{chain.tail}</span>
  return (
    <span className="text-sm">
      {chain.named.map((s, i) => (
        <span key={s.spec}>
          {i > 0 && <span className="mx-1 text-muted-foreground">{chain.seps[i - 1]}</span>}
          <span style={{ color: CLASS_COLORS[specClass(s.spec)] }}>
            {SPEC_SHORT[s.spec] ?? s.spec}
          </span>
        </span>
      ))}
      <span className="mx-1 text-muted-foreground">&gt;</span>
      <span className="text-muted-foreground">{chain.tail}</span>
    </span>
  )
}

function Evidence({
  scores,
  items,
  isToken,
}: {
  scores: SpecScore[]
  items: Record<string, ItemFacts>
  isToken: boolean
}) {
  return (
    <div className="mt-2 overflow-x-auto rounded border border-border bg-muted/30 p-2">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="pr-3 font-medium">Spec</th>
            <th className="pr-3 font-medium">Score</th>
            {isToken && <th className="pr-3 font-medium">Via piece</th>}
            <th className="pr-3 font-medium">Per phase: usage / best alternative</th>
          </tr>
        </thead>
        <tbody>
          {scores.slice(0, 8).map((s) => (
            <tr key={s.spec}>
              <td className="pr-3" style={{ color: CLASS_COLORS[specClass(s.spec)] }}>
                {SPEC_SHORT[s.spec] ?? s.spec}
              </td>
              <td className="pr-3 tabular-nums">{Math.round(s.score)}</td>
              {isToken && (
                <td className="pr-3">{items[s.viaItem]?.name ?? s.viaItem}</td>
              )}
              <td className="pr-3">
                {s.needs
                  .map(
                    (n) =>
                      `P${n.phase}: ${n.usage.toFixed(1)}%` +
                      (n.altId
                        ? ` (alt: ${items[n.altId]?.name ?? "?"} ${n.alt.toFixed(1)}%)`
                        : ""),
                  )
                  .join("  ·  ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Spec-page slot order (SLOT_ORDER), expanded to the raw item slot values. */
const PRIO_SLOT_ORDER = [
  "head",
  "neck",
  "shoulder",
  "back",
  "chest",
  "wrist",
  "hands",
  "waist",
  "legs",
  "feet",
  "finger",
  "trinket",
  "two_hand",
  "main_hand",
  "one_hand",
  "off_hand_weapon",
  "held_off_hand",
  "shield",
  "ranged",
  "thrown",
  "relic",
]

function slotRank(item: ItemFacts, items: Record<string, ItemFacts>): number {
  // Tokens (slot "type-0") sort by the slot of the gear they redeem into.
  const slot =
    item.token && item.redeems?.length ? (items[item.redeems[0]]?.slot ?? item.slot) : item.slot
  const idx = PRIO_SLOT_ORDER.indexOf(slot)
  return idx === -1 ? PRIO_SLOT_ORDER.length : idx
}

function csvEscape(v: string): string {
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
}

function raidCsv(
  encounters: [string, string][],
  rows: Map<string, { item: ItemFacts; chain: Chain }[]>,
): string {
  const lines: string[] = []
  for (const [eid, encName] of encounters) {
    const encRows = rows.get(eid) ?? []
    if (encRows.length === 0) continue
    lines.push(csvEscape(encName))
    lines.push("Item Name,Bias,,,,,,,,Main Raid,Split 1,Split 2")
    for (const { item, chain } of encRows) {
      const cells: string[] = [csvEscape(item.name)]
      chain.named.forEach((s, i) => {
        // A bare "=" cell imports into Sheets/Excel as a broken formula;
        // ="=" is a formula that renders the literal equals sign.
        if (i > 0) cells.push(chain.seps[i - 1] === "=" ? '"=""="""' : chain.seps[i - 1])
        cells.push(SPEC_SHORT[s.spec] ?? s.spec)
      })
      if (chain.named.length > 0) cells.push(">")
      cells.push(chain.tail)
      lines.push(cells.join(","))
    }
    lines.push("")
  }
  return lines.join("\n")
}

function download(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function PrioView({ zone }: { zone: ZoneData }) {
  // Future phases for persistence scoring; chunks load lazily.
  const p4 = useZone("phase-4")
  const p5 = useZone("phase-5")
  const [expanded, setExpanded] = useState<string | null>(null)

  const futureReady = p4 !== undefined && p5 !== undefined
  const computed = useMemo(() => {
    if (!futureReady) return null
    const zones = [zone, p4, p5].filter((z): z is ZoneData => z !== undefined)
    // Item facts across all scored phases (current phase wins) so evidence
    // can name alternatives that only exist in later phases' tables.
    const allItems: Record<string, ItemFacts> = {
      ...(p5?.items ?? {}),
      ...(p4?.items ?? {}),
      ...zone.items,
    }
    const byRaid = new Map<string, [string, string][]>()
    for (const [eid, name] of Object.entries(zone.encounters)) {
      const raid = raidOfEncounter(Number(eid))
      byRaid.set(raid, [...(byRaid.get(raid) ?? []), [eid, name]])
    }
    // Rows per encounter: every lootmap item with its chain.
    const rows = new Map<string, { id: number; item: ItemFacts; scores: SpecScore[]; chain: Chain }[]>()
    for (const [iidStr, facts] of Object.entries(zone.items)) {
      if (!facts.sources?.length) continue
      const iid = Number(iidStr)
      const scores = scoreItem(iid, zones, zone.items)
      const chain = buildChain(scores, Boolean(facts.token))
      for (const eid of facts.sources) {
        const key = String(eid)
        rows.set(key, [...(rows.get(key) ?? []), { id: iid, item: facts, scores, chain }])
      }
    }
    for (const list of rows.values())
      list.sort(
        (a, b) =>
          slotRank(a.item, allItems) - slotRank(b.item, allItems) ||
          (b.chain.named[0]?.score ?? 0) - (a.chain.named[0]?.score ?? 0),
      )
    return { byRaid, rows, allItems }
  }, [zone, p4, p5, futureReady])

  if (!computed)
    return <p className="p-8 text-sm text-muted-foreground">Loading future-phase data…</p>

  return (
    <div className="space-y-6">
      <p className="max-w-3xl text-xs text-muted-foreground">
        Auto-generated loot priority for Phase {zone.anniversaryPhase}: specs are ranked by
        summed need across P{zone.anniversaryPhase}–P5, where need = usage + how far the item
        leads that spec&apos;s best alternative. Objective data only — adjust for tanks,
        professions and roster before use. Expand a row to see the evidence.
        {(() => {
          const cut = Object.keys(zone.specs)
            .filter((s) => !wellSampled(zone).has(s))
            .map((s) => SPEC_SHORT[s] ?? s)
          return cut.length > 0 ? (
            <>
              {" "}
              Excluded for too-small samples (under a third of the phase median):{" "}
              {cut.join(", ")}.
            </>
          ) : null
        })()}
      </p>
      {[...computed.byRaid.entries()].map(([raid, encounters]) => (
        <section key={raid}>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-lg font-bold">{raid}</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                download(
                  `Loot Prio - Phase ${zone.anniversaryPhase} - ${raid}.csv`,
                  raidCsv(
                    encounters,
                    new Map(
                      encounters.map(([eid]) => [
                        eid,
                        (computed.rows.get(eid) ?? []).map(({ item, chain }) => ({ item, chain })),
                      ]),
                    ),
                  ),
                )
              }
            >
              <Download /> Export CSV
            </Button>
          </div>
          <div className="space-y-4">
            {encounters.map(([eid, encName]) => {
              const encRows = computed.rows.get(eid) ?? []
              if (encRows.length === 0) return null
              return (
                <Card key={eid} className="gap-2 py-3">
                  <CardHeader className="px-4">
                    <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
                      {encName}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4">
                    <ul className="space-y-1">
                      {encRows.map(({ id, item, scores, chain }) => {
                        const key = `${eid}-${id}`
                        const open = expanded === key
                        return (
                          <li key={key} className="rounded-md px-2 py-1.5 hover:bg-accent/40">
                            <div className="flex items-center gap-3">
                              <Button
                                variant="ghost"
                                size="icon-xs"
                                className="text-muted-foreground"
                                onClick={() => setExpanded(open ? null : key)}
                              >
                                {open ? <ChevronDown /> : <ChevronRight />}
                              </Button>
                              <a href={wowheadUrl(id)} target="_blank" rel="noreferrer">
                                <img
                                  src={iconUrl(item.icon)}
                                  alt=""
                                  loading="lazy"
                                  className="size-6 rounded border border-border"
                                />
                              </a>
                              <a
                                href={wowheadUrl(id)}
                                target="_blank"
                                rel="noreferrer"
                                className="w-64 shrink-0 truncate text-sm font-medium hover:underline"
                                style={{ color: QUALITY_COLORS[item.quality] }}
                              >
                                {item.name}
                              </a>
                              {item.token && (
                                <Badge
                                  variant="outline"
                                  className="h-4 shrink-0 px-1 text-xs text-emerald-400"
                                >
                                  Token
                                </Badge>
                              )}
                              <ChainText chain={chain} />
                            </div>
                            {open && (
                              <Evidence
                                scores={scores}
                                items={computed.allItems}
                                isToken={Boolean(item.token)}
                              />
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
