import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DISPLAY_FLOOR_PCT, QUALITY_COLORS, iconUrl, wowheadUrl } from "@/lib/wow"
import type { ItemFacts, SlotEntry } from "@/types"

const MAX_ROWS = 8

interface Props {
  label: string
  entries: SlotEntry[]
  items: Record<string, ItemFacts>
}

export function SlotCard({ label, entries, items }: Props) {
  const visible = entries.filter((e) => e.pct >= DISPLAY_FLOOR_PCT && items[e.id]).slice(0, MAX_ROWS)
  if (visible.length === 0) return null
  const topPct = visible[0].pct

  return (
    <Card className="gap-3 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        <ul className="space-y-2">
          {visible.map((entry, rank) => {
            const item = items[entry.id]
            return (
              <li key={entry.id} className="flex items-center gap-3">
                <span className="w-4 text-right text-xs tabular-nums text-muted-foreground">
                  {rank + 1}
                </span>
                <a href={wowheadUrl(entry.id)} target="_blank" rel="noreferrer">
                  <img
                    src={iconUrl(item.icon)}
                    alt=""
                    loading="lazy"
                    className="size-8 rounded border border-border"
                  />
                </a>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <a
                      href={wowheadUrl(entry.id)}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate text-sm font-medium hover:underline"
                      style={{ color: QUALITY_COLORS[item.quality] }}
                      title={`${item.name} (ilvl ${item.itemLevel}) — ${entry.count.toLocaleString()} equipped`}
                    >
                      {item.name}
                    </a>
                    {item.unique && (
                      <Badge variant="outline" className="h-4 px-1 text-[10px] text-amber-400">
                        Unique
                      </Badge>
                    )}
                    {item.uniqueEquipped && (
                      <Badge variant="outline" className="h-4 px-1 text-[10px] text-amber-400">
                        Unique-Equipped
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 h-1 rounded bg-muted">
                    <div
                      className="h-1 rounded bg-primary"
                      style={{ width: `${(entry.pct / topPct) * 100}%` }}
                    />
                  </div>
                </div>
                <span className="w-12 text-right text-sm font-semibold tabular-nums">
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
