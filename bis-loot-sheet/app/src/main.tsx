import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createRouter } from "@tanstack/react-router";
import "./index.css";
import { routeTree } from "./routeTree.gen";

const router = createRouter({
  routeTree,
  // Hovering a link starts loading its route (and zone chunk) immediately.
  defaultPreload: "intent",
  defaultPendingComponent: () => (
    <p className="p-8 text-sm text-muted-foreground">Loading…</p>
  ),
  defaultErrorComponent: ({ error }) => (
    <p className="p-8 text-sm text-destructive">
      Something broke: {error.message}
    </p>
  ),
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
