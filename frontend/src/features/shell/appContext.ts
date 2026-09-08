import { createContext, useContext } from "react";

import type { Category, CurrentUser } from "@/types/domain";

/**
 * State the shell owns and several screens read: the search box in the
 * sidebar, the category the sidebar has selected, and the dialogs that can be
 * opened from more than one place.
 */
export interface AppContextValue {
  user: CurrentUser;
  categories: Category[];
  search: string;
  setSearch: (value: string) => void;
  selectedCategory: number | null;
  setSelectedCategory: (id: number | null) => void;
  openQuickCapture: () => void;
  openCategoryDialog: (category?: Category) => void;
  openReminderDialog: (ideaId: number) => void;
}

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (value === null) {
    throw new Error("useApp must be used inside the application shell.");
  }
  return value;
}
