import { useMemo, useState } from "react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { raidOfEncounter } from "@/lib/wow"
import type { ZoneData } from "@/types"

// Validated against the dark chart surface (dataviz six-checks: all pass).
const KILL_BAR_COLOR = "#d97706"

const chartConfig = {
  kills: { label: "Kills", color: KILL_BAR_COLOR },
} satisfies ChartConfig

function fmtDuration(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
  const s = Math.round(totalSeconds % 60)
  return `${m}:${s.toString().padStart(2, "0")}`
}

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="gap-1 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  )
}

export function Overview({ zone }: { zone: ZoneData }) {
  const { stats } = zone
  const encounterIds = Object.keys(stats.encounters)
  const [encounterId, setEncounterId] = useState(encounterIds[0])
  const encounter = stats.encounters[encounterId]

  // Dense series over the central 99.5% of kills so the tail doesn't stretch
  // the axis; gaps between sparse bins become explicit zeros.
  const series = useMemo(() => {
    if (!encounter) return []
    const total = encounter.durations.reduce((acc, [, n]) => acc + n, 0)
    let cumulative = 0
    let cutoff = Number.POSITIVE_INFINITY
    for (const [bin, n] of encounter.durations) {
      cumulative += n
      if (cumulative / total >= 0.995) {
        cutoff = bin
        break
      }
    }
    const kept = encounter.durations.filter(([bin]) => bin <= cutoff)
    const min = kept[0][0]
    const max = kept[kept.length - 1][0]
    const byBin = new Map(kept)
    const out = []
    for (let bin = min; bin <= max; bin += 15) {
      out.push({ bin, label: fmtDuration(bin), kills: byBin.get(bin) ?? 0 })
    }
    return out
  }, [encounter])

  const raidGroups = useMemo(() => {
    const groups = new Map<string, string[]>()
    for (const id of encounterIds) {
      const raid = raidOfEncounter(Number(id))
      groups.set(raid, [...(groups.get(raid) ?? []), id])
    }
    return groups
  }, [encounterIds])

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <StatTile
          label="Parses analyzed"
          value={stats.rowsKept.toLocaleString()}
          sub="best parse per player, per boss & spec"
        />
        <StatTile
          label="Data updated"
          value={new Date(zone.generatedAt).toLocaleDateString()}
          sub={new Date(zone.generatedAt).toLocaleTimeString()}
        />
      </div>

      <Card className="gap-3 py-4">
        <CardHeader className="flex flex-row items-center justify-between px-4">
          <div>
            <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
              Kill time distribution
            </CardTitle>
            {encounter && (
              <p className="mt-1 text-xs text-muted-foreground">
                {encounter.rows.toLocaleString()} kills · average {fmtDuration(encounter.avgKillMs / 1000)}
              </p>
            )}
          </div>
          <Select value={encounterId} onValueChange={(v) => v && setEncounterId(v)}>
            <SelectTrigger className="w-56">
              <SelectValue>{encounter?.name}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {[...raidGroups.entries()].map(([raid, ids]) => (
                <SelectGroup key={raid}>
                  <SelectLabel>{raid}</SelectLabel>
                  {ids.map((id) => (
                    <SelectItem key={id} value={id}>
                      {stats.encounters[id].name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent className="px-4">
          <ChartContainer config={chartConfig} className="h-64 w-full">
            <BarChart data={series} barCategoryGap={2}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
                minTickGap={40}
              />
              <YAxis tickLine={false} axisLine={false} width={44} />
              <ChartTooltip
                content={<ChartTooltipContent labelFormatter={(label) => `Kill time ${label}`} />}
              />
              <Bar dataKey="kills" fill="var(--color-kills)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  )
}
