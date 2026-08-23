import { createFileRoute, getRouteApi } from "@tanstack/react-router";
import { PrioView } from "@/components/PrioView";
import { loadZone, zoneTags } from "@/lib/data";
import { ZONE_PHASES } from "@/lib/wow";

const phaseRoute = getRouteApi("/$phase");

export const Route = createFileRoute("/$phase/prio")({
  validateSearch: (search: Record<string, unknown>): { raid?: string } => ({
    raid: typeof search.raid === "string" ? search.raid : undefined,
  }),
  // Persistence scoring needs every later phase's data too.
  loader: async ({ params }) => {
    const current = ZONE_PHASES[params.phase] ?? 99;
    const future = zoneTags.filter((t) => (ZONE_PHASES[t] ?? 0) > current);
    return Promise.all(future.map(loadZone));
  },
  pendingComponent: () => (
    <p className="p-8 text-sm text-muted-foreground">
      Loading future-phase data…
    </p>
  ),
  component: PrioPage,
});

function PrioPage() {
  const zone = phaseRoute.useLoaderData();
  const futureZones = Route.useLoaderData();
  const { raid } = Route.useSearch();
  const navigate = Route.useNavigate();
  return (
    <PrioView
      key={zone.zone}
      zone={zone}
      futureZones={futureZones}
      raidSlug={raid}
      onRaidChange={(slug) =>
        navigate({ search: { raid: slug }, replace: true })
      }
    />
  );
}
