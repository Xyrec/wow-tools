import { createFileRoute, getRouteApi } from "@tanstack/react-router";
import { Overview } from "@/components/Overview";

const phaseRoute = getRouteApi("/$phase");

export const Route = createFileRoute("/$phase/")({
  component: () => {
    const zone = phaseRoute.useLoaderData();
    return <Overview key={zone.zone} zone={zone} />;
  },
});
