import { createContext, useContext } from "react";

import type { Theme } from "@/shared/hooks/useTheme";
import type { Category, CurrentUser } from "@/types/domain";

/**
 * State the shell owns and several screens read: the top bar's search, the
 * category the sidebar has selected, the theme, and the dialogs that can be
 * opened from more than one place.
 */
export interface AppContextValue {
  user: CurrentUser;
  categories: Category[];
  search: string;
  setSearch: (value: string) => void;
  /** Kept here so the open search field survives the jump to the idea list. */
  searchOpen: boolean;
  setSearchOpen: (open: boolean) => void;
  theme: Theme;
  setTheme: (theme: Theme) => void;
  unreadCount: number;
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
