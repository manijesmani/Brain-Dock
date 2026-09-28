/**
 * Every route in the application, declared once.
 *
 * The seven screens come straight from the design reference, the trash was
 * added after it, and sign-up shares the login screen. Quick capture, the reminder editor and the
 * category editor are dialogs rather than routes, so they do not appear here.
 */
export const ROUTES = {
  dashboard: "/",
  ideas: "/ideas",
  note: "/ideas/:ideaId",
  archive: "/archive",
  trash: "/trash",
  notifications: "/notifications",
  settings: "/settings",
  // The one login page for every account.
  login: "/panel",
  signup: "/signup",
} as const;

/** Where the login page used to be, kept so old links still arrive. */
export const OLD_LOGIN = "/login";

export type RouteKey = keyof typeof ROUTES;
