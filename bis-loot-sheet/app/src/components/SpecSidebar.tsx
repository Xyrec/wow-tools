import { specKeysByClass } from "@/lib/data"
import { CLASS_COLORS, specName } from "@/lib/wow"
import type { ZoneData } from "@/types"
import { cn } from "@/lib/utils"

interface Props {
  zone: ZoneData
  selected: string
  onSelect: (specKey: string) => void
}

export function SpecSidebar({ zone, selected, onSelect }: Props) {
  const byClass = specKeysByClass(zone)
  return (
    <nav className="space-y-4">
      {[...byClass.entries()].map(([cls, specKeys]) => (
        <div key={cls}>
          <div
            className="mb-1 text-xs font-bold uppercase tracking-wider"
            style={{ color: CLASS_COLORS[cls] }}
          >
            {cls}
          </div>
          <ul>
            {specKeys.map((key) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => onSelect(key)}
                  className={cn(
                    "w-full rounded px-2 py-1 text-left text-sm text-muted-foreground hover:bg-accent hover:text-foreground",
                    key === selected && "bg-accent font-semibold text-foreground",
                  )}
                >
                  {specName(key)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}
