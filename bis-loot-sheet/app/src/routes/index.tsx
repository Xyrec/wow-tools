import { createFileRoute, redirect } from "@tanstack/react-router";
import { zoneTags } from "@/lib/data";

export const Route = createFileRoute("/")({
  beforeLoad: () => {
    // Default to the guild's current phase, else the latest in the build.
    const phase = zoneTags.includes("phase-3") ? "phase-3" : zoneTags.at(-1);
    if (!phase) return;
    throw redirect({ to: "/$phase", params: { phase } });
  },
  component: () => (
    <p className="p-8 text-sm text-muted-foreground">
      No data generated yet — run the pipeline.
    </p>
  ),
});
