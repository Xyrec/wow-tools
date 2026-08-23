import { useEffect } from "react";
import {
  Outlet,
  createFileRoute,
  notFound,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router";
import { SpecSidebar } from "@/components/SpecSidebar";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { loadZone, zoneTags } from "@/lib/data";
import { ZONE_LABELS, ZONE_PHASES } from "@/lib/wow";

declare global {
  interface Window {
    $WowheadPower?: { refreshLinks: () => void };
  }
}

export const Route = createFileRoute("/$phase")({
  loader: async ({ params }) => {
    if (!zoneTags.includes(params.phase)) throw notFound();
    return loadZone(params.phase);
  },
  pendingComponent: () => (
    <p className="p-8 text-sm text-muted-foreground">Loading zone data…</p>
  ),
  component: PhaseLayout,
});

function PhaseLayout() {
  const { phase } = Route.useParams();
  const zone = Route.useLoaderData();
  const navigate = useNavigate();
  const href = useRouterState({ select: (s) => s.location.href });

  // Wowhead's tooltip script only scans on load; re-scan after navigations.
  useEffect(() => {
    const id = setTimeout(() => window.$WowheadPower?.refreshLinks(), 50);
    return () => clearTimeout(id);
  }, [href]);

  return (
    <div className="mx-auto flex max-w-7xl items-start gap-4 px-4">
      {/* Full-height sticky sidebar with its own scrollbar, pinned to the very
          top of the viewport so its bottom is never pushed offscreen. */}
      <div className="sticky top-0 max-h-dvh w-48 shrink-0 overflow-y-auto overscroll-contain py-4 pr-2">
        <SpecSidebar zone={zone} phase={phase} />
      </div>

      <div className="min-w-0 flex-1 py-4">
        <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">
              TBC Item Distribution - from Warcraft Logs
            </h1>
            <p className="max-w-2xl text-xs text-muted-foreground">
              An item distribution list built from Warcraft Logs: what the top
              ~2,000 ranked players of each spec actually wore, and how usage
              splits between items. The higher an item&apos;s equipped&nbsp;%,
              the more likely it is <em>the</em> BiS for that slot - curated BiS
              lists may differ.
            </p>
          </div>
          <Select
            items={zoneTags.map((tag) => ({
              label: `P${ZONE_PHASES[tag] ?? "?"} · ${ZONE_LABELS[tag] ?? tag}`,
              value: tag,
            }))}
            value={phase}
            onValueChange={(v) => {
              if (v)
                navigate({
                  to: ".",
                  params: (prev) => ({ ...prev, phase: v }),
                  search: true,
                });
            }}
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

        <main className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
