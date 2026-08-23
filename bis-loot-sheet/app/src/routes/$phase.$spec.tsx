import { createFileRoute, getRouteApi } from "@tanstack/react-router";
import { PairCard } from "@/components/PairCard";
import { SlotCard } from "@/components/SlotCard";
import { Badge } from "@/components/ui/badge";
import { splitWeapons } from "@/lib/data";
import {
  CLASS_COLORS,
  SLOT_ORDER,
  slugify,
  specClass,
  specName,
  specRole,
} from "@/lib/wow";

const ROLE_CAVEATS: Record<string, string> = {
  healer:
    "Healer rankings are HPS-based. This shows what maximizes healing output on logs, not necessarily what a loot council should value (mana, utility, assignments).",
  tank: "Tank rankings are damage-based. This shows what top-parsing (DPS-focused) tanks wear, not necessarily the mitigation/stamina gear your guild wants tanks in.",
};

const phaseRoute = getRouteApi("/$phase");

export const Route = createFileRoute("/$phase/$spec")({
  component: SpecPage,
});

function SpecPage() {
  const zone = phaseRoute.useLoaderData();
  const { spec: specSlug } = Route.useParams();
  const specKey = Object.keys(zone.specs).find(
    (k) => slugify(k) === specSlug,
  );
  const spec = specKey ? zone.specs[specKey] : undefined;

  if (!specKey || !spec)
    return (
      <p className="text-muted-foreground">
        No data for this spec in this zone.
      </p>
    );

  return (
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
          const slots = splitWeapons(spec.slots, zone.items);
          // Pair-distribution cards follow their singles category.
          const pairAfter: Record<string, [string, string]> = {
            ring: ["ring", "Ring Combinations"],
            trinket: ["trinket", "Trinket Combinations"],
            off_hand: ["weapon", "Weapon Combinations"],
          };
          return SLOT_ORDER.flatMap(([slot, label]) => {
            // 2H/MH cards derive from the shared main-hand pool.
            const nSlot =
              slot === "two_hand" || slot === "main_hand" ? "main_hand" : slot;
            const cards = [
              <SlotCard
                key={slot}
                slot={slot}
                label={label}
                entries={slots[slot] ?? []}
                items={zone.items}
                n={spec.slotN?.[nSlot]}
              />,
            ];
            const pair = pairAfter[slot];
            if (pair && spec.pairs?.[pair[0]]?.length) {
              cards.push(
                <PairCard
                  key={`pair-${pair[0]}`}
                  label={pair[1]}
                  entries={spec.pairs[pair[0]]}
                  items={zone.items}
                  n={spec.pairN?.[pair[0]]}
                />,
              );
            }
            return cards;
          });
        })()}
      </div>
    </>
  );
}
