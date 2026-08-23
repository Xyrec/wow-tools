import { Link } from "@tanstack/react-router";
import { specKeysByClass } from "@/lib/data";
import { CLASS_COLORS, slugify, specName } from "@/lib/wow";
import type { ZoneData } from "@/types";

interface Props {
  zone: ZoneData;
  phase: string;
}

const linkClass =
  "block w-full rounded px-2 py-1 text-left text-sm text-muted-foreground hover:bg-accent hover:text-foreground";
const activeClass = "bg-accent font-semibold text-foreground";

export function SpecSidebar({ zone, phase }: Props) {
  const byClass = specKeysByClass(zone);
  return (
    <nav className="space-y-4">
      <div>
        <Link
          to="/$phase"
          params={{ phase }}
          activeOptions={{ exact: true }}
          className={`${linkClass} font-semibold`}
          activeProps={{ className: activeClass }}
        >
          Overview
        </Link>
        <Link
          to="/$phase/prio"
          params={{ phase }}
          className={`${linkClass} font-semibold`}
          activeProps={{ className: activeClass }}
        >
          Loot priority
        </Link>
      </div>
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
                <Link
                  to="/$phase/$spec"
                  params={{ phase, spec: slugify(key) }}
                  className={linkClass}
                  activeProps={{ className: activeClass }}
                >
                  {specName(key)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
