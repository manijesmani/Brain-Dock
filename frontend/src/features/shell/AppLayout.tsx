import { PlusIcon } from "@phosphor-icons/react";
import { useCallback, useMemo, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { CategoryDialog } from "@/features/categories/CategoryDialog";
import { QuickCaptureDialog } from "@/features/ideas/QuickCaptureDialog";
import { ReminderDialog } from "@/features/reminders/ReminderDialog";
import { AppContext, type AppContextValue } from "@/features/shell/appContext";
import { Sidebar } from "@/features/shell/Sidebar";
import { useCategories, useCurrentUser, useUnreadCount } from "@/shared/api/queries";
import { useSidebar } from "@/shared/hooks/useSidebar";
import { useTheme } from "@/shared/hooks/useTheme";
import type { Category } from "@/types/domain";

export function AppLayout() {
  const location = useLocation();
  const { data: user, isPending, isError } = useCurrentUser();
  const { data: categories = [] } = useCategories();
  const { data: unread } = useUnreadCount({
    // The badge is visible on every screen, so it is polled rather than left
    // to go stale until something else happens to refetch it.
    refetchInterval: 60_000,
  });
  const unreadCount = unread?.count ?? 0;

  const { theme, setTheme } = useTheme();
  const { collapsed, toggle, setCollapsed } = useSidebar();

  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [quickOpen, setQuickOpen] = useState(false);
  const [categoryDialog, setCategoryDialog] = useState<{
    open: boolean;
    category: Category | null;
  }>({ open: false, category: null });
  const [reminderFor, setReminderFor] = useState<number | null>(null);

  const openCategoryDialog = useCallback(
    (category?: Category) => setCategoryDialog({ open: true, category: category ?? null }),
    [],
  );
  const openQuickCapture = useCallback(() => setQuickOpen(true), []);
  const openReminderDialog = useCallback((ideaId: number) => setReminderFor(ideaId), []);

  const isNote = location.pathname.startsWith("/ideas/");

  const context = useMemo<AppContextValue | null>(
    () =>
      user
        ? {
            user,
            categories,
            search,
            setSearch,
            searchOpen,
            setSearchOpen,
            theme,
            setTheme,
            unreadCount,
            selectedCategory,
            setSelectedCategory,
            openQuickCapture,
            openCategoryDialog,
            openReminderDialog,
          }
        : null,
    [
      user,
      categories,
      search,
      searchOpen,
      theme,
      setTheme,
      unreadCount,
      selectedCategory,
      openQuickCapture,
      openCategoryDialog,
      openReminderDialog,
    ],
  );

  if (isPending) {
    return <div className="min-h-screen bg-bd-bg" />;
  }

  // A 403 from /auth/me means there is no session, which is the only way the
  // app learns it needs the login screen.
  if (isError || !context) {
    return <Navigate to={ROUTES.login} replace state={{ from: location.pathname }} />;
  }

  return (
    <AppContext.Provider value={context}>
      <div dir="rtl" className="flex min-h-screen items-stretch bg-bd-bg text-bd-text">
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={toggle}
          categories={categories}
          selectedCategory={selectedCategory}
          onSelectCategory={setSelectedCategory}
          unreadCount={unreadCount}
          onAddCategory={() => openCategoryDialog()}
          onEditCategory={openCategoryDialog}
          onDeleteCategory={(category) => openCategoryDialog(category)}
        />

        <Outlet context={{ setCollapsed }} />

        <button
          type="button"
          onClick={openQuickCapture}
          title="ثبت سریع ایده"
          className="fixed z-[1150] grid size-[67.5px] cursor-pointer place-items-center rounded-full border-0 bg-bd-accent text-bd-accent-ink hover:bg-bd-accent-hover"
          style={{
            left: 35,
            bottom: isNote ? 107.5 : 35,
            boxShadow: "0 12.5px 30px -10px rgba(16,185,129,.5)",
          }}
        >
          <PlusIcon size={30} />
        </button>

        <QuickCaptureDialog
          open={quickOpen}
          onClose={() => setQuickOpen(false)}
          categoryId={selectedCategory}
        />
        <CategoryDialog
          open={categoryDialog.open}
          category={categoryDialog.category}
          onClose={() => setCategoryDialog({ open: false, category: null })}
        />
        <ReminderDialog
          open={reminderFor !== null}
          ideaId={reminderFor}
          onClose={() => setReminderFor(null)}
        />
      </div>
    </AppContext.Provider>
  );
}
