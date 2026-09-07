/**
 * Every route in the application, declared once.
 *
 * The seven screens come straight from the design reference. Quick capture,
 * the reminder editor and the category editor are dialogs rather than routes,
 * so they do not appear here.
 */
export const ROUTES = {
  dashboard: "/",
  ideas: "/ideas",
  note: "/ideas/:ideaId",
  archive: "/archive",
  notifications: "/notifications",
  settings: "/settings",
  login: "/login",
} as const;

export type RouteKey = keyof typeof ROUTES;
