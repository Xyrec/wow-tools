import { Outlet, createRootRoute } from "@tanstack/react-router";

export const Route = createRootRoute({
  component: () => <Outlet />,
  notFoundComponent: () => (
    <p className="p-8 text-sm text-muted-foreground">
      Page not found - pick a phase from the top-right selector.
    </p>
  ),
});
