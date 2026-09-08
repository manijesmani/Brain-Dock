import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "braindock:sidebar-collapsed";

/** Collapsed by default, as the design's own prop schema declares. */
function readStored(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) return stored === "true";
  } catch {
    // Ignored: a remembered layout is a convenience, not state that matters.
  }
  return true;
}

export function useSidebar() {
  const [collapsed, setCollapsed] = useState<boolean>(readStored);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(collapsed));
    } catch {
      // See above.
    }
  }, [collapsed]);

  const toggle = useCallback(() => setCollapsed((current) => !current), []);

  return { collapsed, setCollapsed, toggle };
}
