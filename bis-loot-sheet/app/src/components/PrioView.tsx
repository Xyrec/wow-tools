import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { exportPhaseXlsx } from "@/lib/xlsx";
import {
  buildChain,
  scoreItem,
  wellSampled,
  type Chain,
  type SpecScore,
} from "@/lib/prio";
import {
  CLASS_COLORS,
  QUALITY_COLORS,
  SPEC_SHORT,
  iconUrl,
  raidOfEncounter,
  slugify,
  specClass,
  wowheadUrl,
} from "@/lib/wow";
import type { ItemFacts, ZoneData } from "@/types";

function ChainText({ chain }: { chain: Chain }) {
  if (chain.named.length === 0)
    return <span className="text-sm text-muted-foreground">{chain.tail}</span>;
  return (
    <span className="text-sm">
      {chain.named.map((s, i) => (
        <span key={s.spec}>
          {i > 0 && (
            <span className="mx-1 text-muted-foreground">
              {chain.seps[i - 1]}
            </span>
          )}
          <span style={{ color: CLASS_COLORS[specClass(s.spec)] }}>
            {SPEC_SHORT[s.spec] ?? s.spec}
          </span>
        </span>
      ))}
      <span className="mx-1 text-muted-foreground">&gt;</span>
      <span className="text-muted-foreground">{chain.tail}</span>
    </span>
  );
}

function Evidence({
  scores,
  items,
  isToken,
}: {
  scores: SpecScore[];
  items: Record<string, ItemFacts>;
  isToken: boolean;
}) {
  const phases = [
    ...new Set(scores.flatMap((s) => s.needs.map((n) => n.phase))),
  ].sort();
  return (
    <div className="mt-2 overflow-x-auto rounded border border-border bg-muted/30 p-3">
      <table className="text-xs">
        <thead>
          <tr className="text-muted-foreground">
            <th className="pr-6 text-left font-medium">Spec</th>
            {isToken && <th className="pr-6 text-left font-medium">Gets</th>}
            {phases.map((p) => (
              <th key={p} className="pr-6 text-right font-medium">
                Phase {p}
              </th>
            ))}
            <th className="text-right font-medium">Score</th>
          </tr>
        </thead>
        <tbody>
          {scores.slice(0, 8).map((s) => {
            const byPhase = new Map(s.needs.map((n) => [n.phase, n]));
            return (
              <tr key={s.spec}>
                <td
                  className="pr-6"
                  style={{ color: CLASS_COLORS[specClass(s.spec)] }}
                >
                  {SPEC_SHORT[s.spec] ?? s.spec}
                </td>
                {isToken && (
                  <td className="pr-6">{items[s.viaItem]?.name ?? s.viaItem}</td>
                )}
                {phases.map((p) => {
                  const n = byPhase.get(p);
                  return (
                    <td key={p} className="pr-6 text-right tabular-nums">
                      {n ? `${n.usage.toFixed(1)}%` : "–"}
                    </td>
                  );
                })}
                <td className="text-right tabular-nums">
                  {Math.round(s.score)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted-foreground">
        % = how many of that spec&apos;s top 2,000 players wore this
        {isToken ? " (via the listed piece)" : ""} in that phase. The score
        also rewards items with no good alternative, and counts later phases
        extra - gear that stays best is worth more.
      </p>
    </div>
  );
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
];

function effectiveSlot(
  item: ItemFacts,
  items: Record<string, ItemFacts>,
): string {
  // Tokens (slot "type-0") take the slot of the gear they redeem into.
  return item.token && item.redeems?.length
    ? (items[item.redeems[0]]?.slot ?? item.slot)
    : item.slot;
}

function slotRank(item: ItemFacts, items: Record<string, ItemFacts>): number {
  const idx = PRIO_SLOT_ORDER.indexOf(effectiveSlot(item, items));
  return idx === -1 ? PRIO_SLOT_ORDER.length : idx;
}

/** Competition group for the one-prio-per-slot-per-spec rule: the slot this
 *  spec actually WEARS the item in (from its distribution data), so a 1H
 *  sword a rogue wears off-hand competes with off-hands for the rogue while
 *  competing with main-hands for a spec that wears it main-hand. Dual-
 *  wielders thus hold one main-hand prio and one off-hand prio. */
function wornSlot(s: SpecScore, currentPhase: number): string {
  const n = s.needs.find((x) => x.phase === currentPhase) ?? s.needs[0];
  return n?.slot ?? "?";
}

interface PrioViewProps {
  zone: ZoneData;
  /** Later phases' zones (route loader provides them), for persistence scoring. */
  futureZones: ZoneData[];
  /** Selected raid as a URL slug (search param). */
  raidSlug?: string;
  onRaidChange: (slug: string) => void;
}

export function PrioView({
  zone,
  futureZones,
  raidSlug,
  onRaidChange,
}: PrioViewProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const computed = useMemo(() => {
    const zones = [zone, ...futureZones];
    // Item facts across all scored phases (current phase wins) so evidence
    // can name alternatives that only exist in later phases' tables.
    const allItems: Record<string, ItemFacts> = {};
    for (const z of [...futureZones].reverse()) Object.assign(allItems, z.items);
    Object.assign(allItems, zone.items);
    const byRaid = new Map<string, [string, string][]>();
    for (const [eid, name] of Object.entries(zone.encounters)) {
      const raid = raidOfEncounter(Number(eid));
      byRaid.set(raid, [...(byRaid.get(raid) ?? []), [eid, name]]);
    }
    // Score every droppable item once.
    const itemInfo = new Map<
      number,
      { facts: ItemFacts; scores: SpecScore[] }
    >();
    for (const [iidStr, facts] of Object.entries(zone.items)) {
      if (!facts.sources?.length) continue;
      const iid = Number(iidStr);
      itemInfo.set(iid, { facts, scores: scoreItem(iid, zones, zone.items) });
    }
    // One prio per spec per worn slot across the whole sheet. Dedup by NAMED
    // chain appearances, not raw scores: a spec named on several items it
    // wears in the same slot keeps only its best appearance; removing it
    // elsewhere can promote other specs into those chains, so iterate until
    // stable. This way a spec whose top-scoring item crowds it out (e.g. a
    // shared tier token capped at 4 names) still lands on the next item down
    // instead of losing the slot.
    const currentPhase = zone.anniversaryPhase;
    const removed = new Map<number, Set<string>>();
    const keptScores = (iid: number): SpecScore[] => {
      const info = itemInfo.get(iid);
      if (!info) return [];
      const gone = removed.get(iid);
      return gone ? info.scores.filter((s) => !gone.has(s.spec)) : info.scores;
    };
    for (let changed = true; changed; ) {
      changed = false;
      const bestApp = new Map<string, { iid: number; score: number }>();
      const apps = new Map<string, number[]>();
      for (const [iid, info] of itemInfo) {
        for (const s of buildChain(keptScores(iid), Boolean(info.facts.token))
          .named) {
          const key = `${s.spec}|${wornSlot(s, currentPhase)}`;
          apps.set(key, [...(apps.get(key) ?? []), iid]);
          const cur = bestApp.get(key);
          if (
            !cur ||
            s.score > cur.score ||
            (s.score === cur.score && iid < cur.iid)
          )
            bestApp.set(key, { iid, score: s.score });
        }
      }
      for (const [key, list] of apps) {
        const spec = key.slice(0, key.indexOf("|"));
        for (const iid of list) {
          if (iid === bestApp.get(key)?.iid) continue;
          const gone = removed.get(iid) ?? new Set<string>();
          if (!gone.has(spec)) {
            gone.add(spec);
            removed.set(iid, gone);
            changed = true;
          }
        }
      }
    }
    // Items sharing a name (the two Warglaives) get their hand appended so
    // the sheet says which is which.
    const nameCount = new Map<string, number>();
    for (const { facts } of itemInfo.values())
      nameCount.set(facts.name, (nameCount.get(facts.name) ?? 0) + 1);
    const HAND_LABEL: Record<string, string> = {
      two_hand: "Two Hand",
      main_hand: "Main Hand",
      one_hand: "One Hand",
      off_hand_weapon: "Off Hand",
      held_off_hand: "Off Hand",
      shield: "Off Hand",
    };
    // Rows per encounter with dedup-filtered chains.
    const rows = new Map<
      string,
      { id: number; item: ItemFacts; scores: SpecScore[]; chain: Chain }[]
    >();
    for (const [iid, info] of itemInfo) {
      const kept = keptScores(iid);
      const chain = buildChain(kept, Boolean(info.facts.token));
      const item =
        (nameCount.get(info.facts.name) ?? 0) > 1 &&
        HAND_LABEL[info.facts.slot]
          ? { ...info.facts, name: `${info.facts.name} (${HAND_LABEL[info.facts.slot]})` }
          : info.facts;
      for (const eid of info.facts.sources ?? []) {
        const key = String(eid);
        rows.set(key, [
          ...(rows.get(key) ?? []),
          { id: iid, item, scores: kept, chain },
        ]);
      }
    }
    for (const list of rows.values())
      list.sort(
        (a, b) =>
          slotRank(a.item, allItems) - slotRank(b.item, allItems) ||
          (b.chain.named[0]?.score ?? 0) - (a.chain.named[0]?.score ?? 0),
      );
    return { byRaid, rows, allItems };
  }, [zone, futureZones]);

  return (
    <div className="space-y-6">
      <p className="max-w-3xl text-xs text-muted-foreground">
        Auto-generated loot priority for Phase {zone.anniversaryPhase}: specs
        are ranked by summed need across P{zone.anniversaryPhase}–P5, where need
        = usage + how far the item leads that spec&apos;s best alternative, and
        each future phase weighs ×1.5 more than the last - items that stay
        useful later are worth more now.
        Objective data only - adjust for tanks, professions and roster before
        use. Expand a row to see the evidence.
        {(() => {
          const cut = Object.keys(zone.specs)
            .filter((s) => !wellSampled(zone).has(s))
            .map((s) => SPEC_SHORT[s] ?? s);
          return cut.length > 0 ? (
            <>
              {" "}
              Excluded for too-small samples (under a third of the phase
              median): {cut.join(", ")}.
            </>
          ) : null;
        })()}
      </p>
      {(() => {
        const raidNames = [...computed.byRaid.keys()];
        const active =
          raidNames.find((r) => slugify(r) === raidSlug) ?? raidNames[0] ?? "";
        const encounters = computed.byRaid.get(active) ?? [];
        return (
          <section key={active}>
            <div className="mb-2 flex items-center justify-between gap-3">
              <Select
                items={raidNames.map((r) => ({ label: r, value: r }))}
                value={active}
                onValueChange={(v) => v && onRaidChange(slugify(v))}
              >
                <SelectTrigger className="w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent alignItemWithTrigger={false}>
                  <SelectGroup>
                    {raidNames.map((r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  exportPhaseXlsx(
                    zone.anniversaryPhase,
                    [...computed.byRaid.entries()].map(([raid, encs]) => ({
                      raid,
                      encounters: encs,
                      rows: new Map(
                        encs.map(([eid]) => [
                          eid,
                          (computed.rows.get(eid) ?? []).map(
                            ({ item, chain }) => ({ item, chain }),
                          ),
                        ]),
                      ),
                    })),
                  )
                }
              >
                <Download /> Export XLSX
              </Button>
            </div>
            <div className="space-y-4">
              {encounters.map(([eid, encName]) => {
                const encRows = computed.rows.get(eid) ?? [];
                if (encRows.length === 0) return null;
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
                          const key = `${eid}-${id}`;
                          const open = expanded.has(key);
                          return (
                            <li
                              key={key}
                              className="rounded-md px-2 py-1.5 hover:bg-accent/40"
                            >
                              <div className="flex items-center gap-3">
                                <Button
                                  variant="ghost"
                                  size="icon-xs"
                                  className="text-muted-foreground"
                                  onClick={() =>
                                    setExpanded((prev) => {
                                      const next = new Set(prev);
                                      if (open) next.delete(key);
                                      else next.add(key);
                                      return next;
                                    })
                                  }
                                >
                                  {open ? <ChevronDown /> : <ChevronRight />}
                                </Button>
                                <a
                                  href={wowheadUrl(id)}
                                  target="_blank"
                                  rel="noreferrer"
                                >
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
                                  style={{
                                    color: QUALITY_COLORS[item.quality],
                                  }}
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
                          );
                        })}
                      </ul>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </section>
        );
      })()}
    </div>
  );
}
