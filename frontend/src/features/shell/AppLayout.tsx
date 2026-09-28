import { PlusIcon, WarningCircleIcon } from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { CategoryDialog } from "@/features/categories/CategoryDialog";
import { QuickCaptureDialog } from "@/features/ideas/QuickCaptureDialog";
import { SubscribeDialog } from "@/features/plans/SubscribeDialog";
import { ReminderDialog } from "@/features/reminders/ReminderDialog";
import { AppContext, type AppContextValue } from "@/features/shell/appContext";
import { Sidebar } from "@/features/shell/Sidebar";
import { errorStatus } from "@/shared/api/errors";
import { useCategories, useCurrentUser, useStartGuest, useUnreadCount } from "@/shared/api/queries";
import { DESKTOP_QUERY, useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { useSidebar } from "@/shared/hooks/useSidebar";
import { useTheme } from "@/shared/hooks/useTheme";
import { hasSignedInHere, rememberSignIn } from "@/shared/lib/account";
import { ToastProvider } from "@/shared/ui/Toast";
import type { Category } from "@/types/domain";

export function AppLayout() {
  const location = useLocation();
  const { data: user, isPending, isError, error } = useCurrentUser();
  const { data: categories = [] } = useCategories();
  const { data: unread } = useUnreadCount({
    // The badge is visible on every screen, so it is polled rather than left
    // to go stale until something else happens to refetch it.
    refetchInterval: 60_000,
  });
  const unreadCount = unread?.count ?? 0;

  const { theme, setTheme } = useTheme();
  const { collapsed, toggle, setCollapsed } = useSidebar();
  const desktop = useMediaQuery(DESKTOP_QUERY);

  // Below the desktop width the sidebar is a drawer. It remembers the page it
  // was opened on, so going anywhere else -- the back gesture included --
  // closes it without an effect having to notice the navigation.
  const [navOpenedAt, setNavOpenedAt] = useState<string | null>(null);
  const navOpen = !desktop && navOpenedAt === location.pathname;
  const openNav = useCallback(() => setNavOpenedAt(location.pathname), [location.pathname]);
  const closeNav = useCallback(() => setNavOpenedAt(null), []);

  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [quickOpen, setQuickOpen] = useState(false);
  const [categoryDialog, setCategoryDialog] = useState<{
    open: boolean;
    category: Category | null;
  }>({ open: false, category: null });
  const [reminderFor, setReminderFor] = useState<number | null>(null);
  const [subscribeOpen, setSubscribeOpen] = useState(false);

  const openCategoryDialog = useCallback(
    (category?: Category) => setCategoryDialog({ open: true, category: category ?? null }),
    [],
  );
  const openQuickCapture = useCallback(() => setQuickOpen(true), []);
  const openReminderDialog = useCallback((ideaId: number) => setReminderFor(ideaId), []);

  const isNote = location.pathname.startsWith("/ideas/");

  // Also covers sessions that began before this was remembered at sign-in.
  useEffect(() => {
    if (user && user.plan !== "guest") rememberSignIn();
  }, [user]);

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
            openNav,
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
      openNav,
    ],
  );

  if (isPending) {
    return <div className="min-h-page bg-bd-bg" />;
  }

  // A 403 from /auth/me means there is no session. Someone new goes straight
  // into a guest account, so the app can be used without one; someone who
  // has signed in on this browser before is asked to sign in again.
  if (isError || !context) {
    if (errorStatus(error) === 403 && !hasSignedInHere()) return <GuestStart />;
    return <Navigate to={ROUTES.login} replace state={{ from: location.pathname }} />;
  }

  return (
    <AppContext.Provider value={context}>
      {/* Raised on the note page, clear of the editor's toolbar. */}
      <ToastProvider raised={isNote}>
        <div dir="rtl" className="flex min-h-page items-stretch bg-bd-bg text-bd-text">
          <Sidebar
            user={context.user}
            collapsed={collapsed}
            onToggleCollapse={toggle}
            drawer={!desktop}
            open={navOpen}
            onClose={closeNav}
            categories={categories}
            selectedCategory={selectedCategory}
            onSelectCategory={setSelectedCategory}
            unreadCount={unreadCount}
            onAddCategory={() => openCategoryDialog()}
            onEditCategory={openCategoryDialog}
            onDeleteCategory={(category) => openCategoryDialog(category)}
            onSubscribe={() => setSubscribeOpen(true)}
          />

          {/* The page, under the guest banner when there is one. */}
          <div className="flex min-w-0 flex-1 flex-col">
            {context.user.plan === "guest" ? <GuestBanner /> : null}
            <Outlet context={{ setCollapsed }} />
          </div>

          {/* Smaller and closer to the corner on a phone. On the note page it
            sits above the editor toolbar, which is shorter there too. */}
          <button
            type="button"
            onClick={openQuickCapture}
            title="ثبت سریع ایده"
            className={`fixed left-4 z-[1150] grid size-14 cursor-pointer place-items-center rounded-full border-0 bg-bd-accent text-bd-accent-ink hover:bg-bd-accent-hover lg:left-[28px] lg:size-[54px] ${
              isNote ? "bottom-[70.5px] lg:bottom-[86px]" : "bottom-4 lg:bottom-[28px]"
            }`}
            style={{ boxShadow: "0 10px 24px -8px rgba(16,185,129,.5)" }}
          >
            <PlusIcon size={desktop ? 24 : 21} />
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
          <SubscribeDialog open={subscribeOpen} onClose={() => setSubscribeOpen(false)} />
        </div>
      </ToastProvider>
    </AppContext.Provider>
  );
}

/**
 * Opens a guest account for a first visit. The app appears as soon as it
 * exists, because starting it fills in the current user.
 */
function GuestStart() {
  const { mutate, isError } = useStartGuest();
  const started = useRef(false);

  useEffect(() => {
    // Once, although development runs every effect twice.
    if (started.current) return;
    started.current = true;
    mutate();
  }, [mutate]);

  // Refused -- most likely too many new guests from one address. Signing in
  // or up on the login page still works.
  if (isError) return <Navigate to={ROUTES.login} replace />;
  return <div className="min-h-page bg-bd-bg" />;
}

/**
 * Above every page for as long as someone is a guest, with no way to dismiss
 * it: a guest's ideas live only behind this browser's cookie until it signs
 * up.
 */
function GuestBanner() {
  const navigate = useNavigate();

  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b px-4 py-2.5 sm:px-6 lg:px-[38px]"
      style={{ background: "var(--color-bd-warn-bg)", borderColor: "var(--color-bd-border)" }}
    >
      <WarningCircleIcon size={18} className="flex-none text-bd-warn" />
      <span className="min-w-0 flex-1 text-[13px] leading-[1.7] font-medium text-bd-warn">
        برای حفظ اطلاعاتتان یک حساب کاربری بسازید.
      </span>
      <button
        type="button"
        onClick={() => void navigate(ROUTES.signup)}
        className="h-8 flex-none cursor-pointer rounded-button border-0 bg-bd-accent px-3.5 text-[12.5px] font-semibold text-bd-accent-ink hover:bg-bd-accent-hover"
      >
        ساخت حساب
      </button>
    </div>
  );
}
