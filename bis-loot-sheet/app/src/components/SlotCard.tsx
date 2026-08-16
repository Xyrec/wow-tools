import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  BIS_TIE_WINDOW,
  DISPLAY_FLOOR_PCT,
  QUALITY_COLORS,
  ZONE_PHASES,
  iconUrl,
  wowheadUrl,
} from "@/lib/wow"
import { cn } from "@/lib/utils"
import type { ItemFacts, SlotEntry } from "@/types"

const MAX_ROWS = 8

// Unique matters where a player could otherwise equip two of the same item.
const DUPLICATE_SLOTS = new Set(["ring", "trinket", "main_hand", "off_hand"])

interface Props {
  slot: string
  label: string
  entries: SlotEntry[]
  items: Record<string, ItemFacts>
}

export function SlotCard({ slot, label, entries, items }: Props) {
  const visible = entries
    .filter((e) => e.pct >= DISPLAY_FLOOR_PCT && items[e.id])
    .slice(0, MAX_ROWS)
  if (visible.length === 0) return null
  const topPct = visible[0].pct
  const showUnique = DUPLICATE_SLOTS.has(slot)

  return (
    <Card className="gap-3 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        <ul className="space-y-1">
          {visible.map((entry, rank) => {
            const item = items[entry.id]
            const isBis = topPct - entry.pct <= BIS_TIE_WINDOW
            return (
              <li
                key={entry.id}
                className={cn(
                  "flex items-center gap-3 rounded-md px-2 py-1.5",
                  isBis && "bg-amber-400/10 ring-1 ring-amber-400/30",
                )}
              >
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
                    >
                      {item.name}
                    </a>
                    {item.laterPhase && (
                      <Badge variant="destructive" className="h-4 px-1 text-[10px]">
                        P{ZONE_PHASES[item.laterPhase] ?? "?"} item
                      </Badge>
                    )}
                    {item.pvp && (
                      <Badge variant="outline" className="h-4 px-1 text-[10px] text-sky-400">
                        PvP
                      </Badge>
                    )}
                    {item.setId && (
                      <Badge variant="outline" className="h-4 px-1 text-[10px] text-emerald-400">
                        {item.token ? "Token" : "Set Piece"}
                      </Badge>
                    )}
                    {showUnique && item.unique && (
                      <Badge variant="outline" className="h-4 px-1 text-[10px] text-amber-400">
                        Unique
                      </Badge>
                    )}
                    {showUnique && item.uniqueEquipped && (
                      <Badge variant="outline" className="h-4 px-1 text-[10px] text-amber-400">
                        Unique-Equipped
                      </Badge>
                    )}
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
                  title={`${entry.count.toLocaleString()} equipped`}
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
