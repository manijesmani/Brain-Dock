import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "braindock:theme";

/**
 * Theme lives in the browser, not on the user record.
 *
 * Switching has to be instant and it is a property of the device rather than
 * the account, so a round trip to the server would only add latency to
 * something that must feel immediate.
 */
function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // Private windows and blocked site data both throw; light is the default.
  }
  // Matches the class index.html stamps before React runs, so a first visit
  // never flashes the dark palette.
  return "light";
}

function applyTheme(theme: Theme): void {
  // Light is opted into by a class, exactly as the design file does it.
  document.documentElement.classList.toggle("bd-light", theme === "light");
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Not being able to remember the choice is not worth failing over.
    }
  }, [theme]);

  const setTheme = useCallback((next: Theme) => setThemeState(next), []);

  return { theme, setTheme };
}
