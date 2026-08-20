import { Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { BIS_TIE_WINDOW, DISPLAY_FLOOR_PCT, QUALITY_COLORS, iconUrl, wowheadUrl } from "@/lib/wow"
import type { ItemFacts, PairEntry } from "@/types"

const MAX_ROWS = 8

function PairItem({ id, items }: { id: number | null; items: Record<string, ItemFacts> }) {
  if (id === null)
    return <span className="text-xs italic text-muted-foreground">— (two-handed)</span>
  const item = items[id]
  if (!item) return null
  return (
    <span className="flex min-w-0 items-center gap-2">
      <a href={wowheadUrl(id)} target="_blank" rel="noreferrer" className="shrink-0">
        <img src={iconUrl(item.icon)} alt="" loading="lazy" className="size-6 rounded border border-border" />
      </a>
      <a
        href={wowheadUrl(id)}
        target="_blank"
        rel="noreferrer"
        className="truncate text-xs font-medium hover:underline"
        style={{ color: QUALITY_COLORS[item.quality] }}
      >
        {item.name}
      </a>
    </span>
  )
}

interface Props {
  label: string
  entries: PairEntry[]
  items: Record<string, ItemFacts>
  n?: number
}

/** Distribution of item COMBINATIONS for two-slot categories (rings,
 *  trinkets, weapons) — which exact pair top players actually run. */
export function PairCard({ label, entries, items, n }: Props) {
  const visible = entries
    .filter((e) => e.pct >= DISPLAY_FLOOR_PCT && items[e.a] && (e.b === null || items[e.b]))
    .slice(0, MAX_ROWS)
  if (visible.length === 0) return null
  const topPct = visible[0].pct

  return (
    <Card className="gap-3 py-4">
      <CardHeader className="flex flex-row items-baseline justify-between px-4">
        <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
          {label}
        </CardTitle>
        {n !== undefined && (
          <Tooltip>
            <TooltipTrigger
              render={
                <Button variant="ghost" size="icon-sm" className="text-muted-foreground" />
              }
            >
              <Info />
              <span className="sr-only">Sample size</span>
            </TooltipTrigger>
            <TooltipContent>
              n = {n.toLocaleString()} — phase-pure player loadouts contributing to these combinations
            </TooltipContent>
          </Tooltip>
        )}
      </CardHeader>
      <CardContent className="px-4">
        <ul className="space-y-1">
          {visible.map((entry, rank) => {
            const isBis = topPct - entry.pct <= BIS_TIE_WINDOW
            return (
              <li
                key={`${entry.a}-${entry.b}`}
                className={cn(
                  "flex items-center gap-3 rounded-md px-2 py-1.5",
                  isBis && "bg-amber-400/10 ring-1 ring-amber-400/30",
                )}
              >
                <span className="w-4 text-right text-xs tabular-nums text-muted-foreground">
                  {rank + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="grid grid-cols-2 items-center gap-2">
                    <PairItem id={entry.a} items={items} />
                    <PairItem id={entry.b} items={items} />
                  </div>
                  <div className="mt-1 h-1 rounded bg-muted">
                    <div
                      className={cn("h-1 rounded", isBis ? "bg-amber-400" : "bg-primary/60")}
                      style={{ width: `${(entry.pct / topPct) * 100}%` }}
                    />
                  </div>
                </div>
                <span
                  className={cn(
                    "w-12 text-right text-sm font-semibold tabular-nums",
                    isBis && "text-amber-300",
                  )}
                  title={`${entry.count.toLocaleString()} players`}
                >
                  {entry.pct.toFixed(1)}%
                </span>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}
