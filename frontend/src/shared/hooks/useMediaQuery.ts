import { useSyncExternalStore } from "react";

/**
 * Tailwind's `lg` breakpoint. At this width and above the sidebar sits beside
 * the page; below it, it becomes a drawer over the page.
 */
export const DESKTOP_QUERY = "(min-width: 64rem)";

/** Whether a media query matches, kept in step as the window is resized. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
  );
}
