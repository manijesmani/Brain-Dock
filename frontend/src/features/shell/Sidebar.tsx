import {
  ArchiveIcon,
  BellIcon,
  BrainIcon,
  CrownSimpleIcon,
  DotsThreeIcon,
  GaugeIcon,
  GearIcon,
  LightbulbIcon,
  PaletteIcon,
  PencilSimpleIcon,
  PlusIcon,
  SidebarSimpleIcon,
  TrashIcon,
  XIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { toPersianDigits } from "@/shared/lib/persian";
import type { Category, CurrentUser } from "@/types/domain";

const EXPANDED_WIDTH = 250;
const COLLAPSED_WIDTH = 66;

const NAV = [
  { path: ROUTES.ideas, label: "همهٔ ایده‌ها", Icon: LightbulbIcon },
  { path: ROUTES.dashboard, label: "داشبورد", Icon: GaugeIcon },
  { path: ROUTES.archive, label: "آرشیو", Icon: ArchiveIcon },
  { path: ROUTES.trash, label: "سطل زباله", Icon: TrashIcon },
  { path: ROUTES.notifications, label: "اعلان‌ها", Icon: BellIcon },
  { path: ROUTES.settings, label: "تنظیمات", Icon: GearIcon },
] as const;

interface SidebarProps {
  user: CurrentUser;
  collapsed: boolean;
  onToggleCollapse: () => void;
  /**
   * Below the desktop width the sidebar leaves the page and slides in over it
   * instead: always expanded, closed until `open`, and closed again by a
   * choice, the backdrop or Escape.
   */
  drawer: boolean;
  open: boolean;
  onClose: () => void;
  categories: Category[];
  selectedCategory: number | null;
  onSelectCategory: (id: number | null) => void;
  unreadCount: number;
  onAddCategory: () => void;
  onEditCategory: (category: Category) => void;
  onDeleteCategory: (category: Category) => void;
  /** Opens «خرید اشتراک»; the dialog lives in the shell, outside the drawer. */
  onSubscribe: () => void;
}

export function Sidebar({
  user,
  collapsed,
  onToggleCollapse,
  drawer,
  open,
  onClose,
  categories,
  selectedCategory,
  onSelectCategory,
  unreadCount,
  onAddCategory,
  onEditCategory,
  onDeleteCategory,
  onSubscribe,
}: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const expanded = drawer || !collapsed;
  const [openMenu, setOpenMenu] = useState<number | null>(null);
  const owner = user.plan === "owner";
  // The note page's toolbar runs the full width of the window, across the
  // foot of the sidebar, so there the sidebar stops short of it.
  const aboveToolbar = !drawer && location.pathname.startsWith("/ideas/");

  // While the drawer is out it owns the screen: Escape closes it and the page
  // behind stays put, as it does under a dialog.
  useEffect(() => {
    if (!drawer || !open) return;

    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", close);

    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", close);
      document.body.style.overflow = overflow;
    };
  }, [drawer, open, onClose]);

  const go = (path: string) => {
    void navigate(path);
    if (drawer) onClose();
  };

  const isActive = (path: string) =>
    path === ROUTES.ideas
      ? location.pathname === path && selectedCategory === null
      : location.pathname === path;

  // The active item is a tab cut out of the sidebar into the page beside it.
  // In the drawer there is no page beside it, so the item is lit in place.
  const activeItem = drawer
    ? "me-2 rounded-[9px] bg-bd-sb-active font-semibold text-bd-sb-fg"
    : "me-0 bg-bd-bg font-semibold text-bd-accent";

  return (
    <>
      {drawer && open ? (
        <div className="fixed inset-0 z-[1360] bg-black/50" onClick={onClose} />
      ) : null}

      <aside
        inert={drawer && !open}
        className={`flex flex-col overflow-hidden bg-bd-sb-bg text-bd-sb-fg ${
          drawer
            ? `fixed inset-y-0 start-0 z-[1370] h-page w-[min(250px,86vw)] transition-transform duration-200 ${
                open ? "translate-x-0 shadow-bd-lg" : "translate-x-full"
              }`
            : `sticky top-0 h-page flex-none transition-[width] duration-200 ${
                aboveToolbar ? "pb-[53px]" : ""
              }`
        }`}
        style={{
          width: drawer ? undefined : expanded ? EXPANDED_WIDTH : COLLAPSED_WIDTH,
          transitionTimingFunction: "cubic-bezier(.4,0,.2,1)",
        }}
      >
        <div className="flex items-center gap-2.5 px-[13px] pt-[18px] pb-4">
          <div className="flex flex-none flex-col items-center gap-1.5">
            {/* With the sidebar collapsed the mark is also the way back out. */}
            <button
              type="button"
              title={expanded ? "BrainDock" : "باز کردن نوار"}
              onClick={() => {
                if (collapsed && !drawer) onToggleCollapse();
              }}
              className={`grid size-[30px] flex-none place-items-center rounded-[9px] border-0 bg-bd-sb-fg p-0 text-bd-sb-bg ${
                expanded ? "cursor-default" : "cursor-pointer"
              }`}
            >
              <BrainIcon size={18} />
            </button>
            {/* Too narrow for it beside the mark, so it goes underneath. */}
            {owner && !expanded ? <OwnerBadge compact /> : null}
          </div>
          {expanded ? (
            <>
              <span className="font-wordmark text-[16.5px] font-bold tracking-tight whitespace-nowrap">
                BrainDock
              </span>
              {owner ? <OwnerBadge /> : null}
              <span className="flex-1" />
              <button
                type="button"
                onClick={drawer ? onClose : onToggleCollapse}
                title={drawer ? "بستن منو" : "جمع کردن نوار"}
                className="grid size-7 flex-none cursor-pointer place-items-center rounded-button border-0 bg-transparent text-bd-sb-fg-3 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
              >
                {drawer ? <XIcon size={16} /> : <SidebarSimpleIcon size={16} />}
              </button>
            </>
          ) : null}
        </div>

        <nav className="flex flex-col gap-1 ps-2 pointer-coarse:gap-1.5">
          {NAV.map(({ path, label, Icon }) => {
            const active = isActive(path);
            return (
              <button
                key={path}
                type="button"
                title={label}
                onClick={() => {
                  if (path === ROUTES.ideas) onSelectCategory(null);
                  go(path);
                }}
                className={`relative flex h-[38px] cursor-pointer items-center gap-[11px] border-0 px-[11px] text-[13.5px] transition-colors ${
                  active
                    ? `${activeItem} ${drawer ? "" : "rounded-[0_24px_24px_0]"}`
                    : "me-2 rounded-[9px] bg-transparent text-bd-sb-fg-2 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
                }`}
              >
                {active && !drawer ? <TabCorners /> : null}
                <Icon size={19} className="flex-none" />
                {expanded ? (
                  <span className="flex-1 text-right whitespace-nowrap">{label}</span>
                ) : null}
                {path === ROUTES.notifications && unreadCount > 0 ? (
                  <span
                    className={`grid h-[18px] min-w-[18px] flex-none place-items-center rounded-full px-[5px] text-[11px] font-semibold ${
                      active ? "bg-bd-accent text-bd-accent-ink" : "bg-bd-sb-fg text-bd-sb-bg"
                    }`}
                  >
                    {toPersianDigits(unreadCount)}
                  </span>
                ) : null}
              </button>
            );
          })}
        </nav>

        <div className="mx-3 mt-[14px] mb-3 h-px bg-bd-sb-line" />

        {/* The vertical padding, pulled back by the negative margin, leaves room
          for a selected category's tab corners inside the scrolling area. */}
        <div className="-mt-4 min-h-0 flex-1 overflow-y-auto py-4 ps-2">
          {expanded ? (
            <div className="px-[11px] pt-0.5 pb-2 text-[11.5px] font-semibold text-bd-sb-fg-3">
              دسته‌بندی‌ها
            </div>
          ) : null}

          {categories.map((category) => {
            // Only one tab at a time: a category is the tab while it is being
            // browsed, and "all ideas" then gives the tab up.
            const selected = selectedCategory === category.id && location.pathname === ROUTES.ideas;
            const tab = selected && !drawer;
            return (
              <div key={category.id} className={`relative mb-0.5 ${tab ? "me-0" : "me-2"}`}>
                <button
                  type="button"
                  title={category.name}
                  onClick={() => {
                    onSelectCategory(category.id);
                    go(ROUTES.ideas);
                  }}
                  className={`relative flex h-[34px] w-full cursor-pointer items-center gap-[11px] border-0 px-[11px] text-[13px] transition-colors ${
                    tab
                      ? "rounded-[0_21px_21px_0] bg-bd-bg font-semibold text-bd-accent"
                      : selected
                        ? "rounded-button bg-bd-sb-active font-semibold text-bd-sb-fg"
                        : "rounded-button bg-transparent text-bd-sb-fg-2 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
                  }`}
                >
                  {tab ? <TabCorners /> : null}
                  <span
                    className="size-2 flex-none rounded-full"
                    style={{
                      background: category.color,
                      boxShadow: tab
                        ? `0 0 0 3px ${category.color}22`
                        : "0 0 0 1.5px var(--color-bd-sb-fg)",
                    }}
                  />
                  {expanded ? (
                    <>
                      <span className="flex-1 overflow-hidden text-right text-ellipsis whitespace-nowrap">
                        {category.name}
                      </span>
                      <span
                        className={`flex-none pe-[22px] text-[11.5px] font-normal ${
                          tab ? "text-bd-text-3" : "text-bd-sb-fg-3"
                        }`}
                      >
                        {toPersianDigits(category.idea_count)}
                      </span>
                    </>
                  ) : null}
                </button>

                {expanded ? (
                  <button
                    type="button"
                    title="گزینه‌های دسته"
                    onClick={(event) => {
                      event.stopPropagation();
                      setOpenMenu(openMenu === category.id ? null : category.id);
                    }}
                    className={`absolute end-1.5 top-1.5 grid size-[22px] cursor-pointer place-items-center rounded-[6px] border-0 bg-transparent ${
                      tab
                        ? "text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
                        : "text-bd-sb-fg-3 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
                    }`}
                  >
                    <DotsThreeIcon size={16} />
                  </button>
                ) : null}

                {openMenu === category.id ? (
                  <>
                    <div className="fixed inset-0 z-[1200]" onClick={() => setOpenMenu(null)} />
                    <div
                      className="absolute end-1.5 top-8 z-[1300] min-w-[158px] rounded-card border border-bd-border-2 bg-bd-surface-2 p-[5px] shadow-bd-lg"
                      style={{ animation: "bd-pop 150ms ease-out" }}
                    >
                      <MenuItem
                        icon={<PencilSimpleIcon size={15} />}
                        onClick={() => {
                          setOpenMenu(null);
                          onEditCategory(category);
                        }}
                      >
                        ویرایش نام
                      </MenuItem>
                      <MenuItem
                        icon={<PaletteIcon size={15} />}
                        onClick={() => {
                          setOpenMenu(null);
                          onEditCategory(category);
                        }}
                      >
                        تغییر رنگ
                      </MenuItem>
                      <span className="mx-1 my-[5px] block h-px bg-bd-border" />
                      <MenuItem
                        icon={<TrashIcon size={15} />}
                        danger
                        onClick={() => {
                          setOpenMenu(null);
                          onDeleteCategory(category);
                        }}
                      >
                        حذف دسته
                      </MenuItem>
                    </div>
                  </>
                ) : null}
              </div>
            );
          })}

          <button
            type="button"
            title="دستهٔ جدید"
            onClick={onAddCategory}
            className="mt-1 flex h-[34px] w-[calc(100%-8px)] cursor-pointer items-center gap-[11px] rounded-button border-0 bg-transparent px-[11px] text-[13px] text-bd-sb-fg-3 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
          >
            <span className="grid w-2 flex-none place-items-center">
              <PlusIcon size={16} />
            </span>
            {expanded ? <span className="whitespace-nowrap">دستهٔ جدید</span> : null}
          </button>
        </div>

        {expanded && user.idea_limit !== null ? <PlanCard user={user} /> : null}

        {/* Guests and regular accounts: the way to become special. */}
        {user.plan === "guest" || user.plan === "free" ? (
          <SubscribeItem
            expanded={expanded}
            onClick={() => {
              onSubscribe();
              if (drawer) onClose();
            }}
          />
        ) : null}
      </aside>
    </>
  );
}

/** Marks the site owner's account, and no other, beside the logo. */
function OwnerBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`flex-none rounded-full bg-bd-sb-fg font-semibold whitespace-nowrap text-bd-sb-bg ${
        compact ? "px-1.5 text-[10px] leading-4" : "px-2 py-px text-[11px]"
      }`}
    >
      مالک
    </span>
  );
}

/**
 * How much of its idea allowance a guest or a regular account has used. A
 * guest is also shown the banner above every page, asking it to sign up.
 */
function PlanCard({ user }: { user: CurrentUser }) {
  const limit = user.idea_limit ?? 0;
  const used = Math.min(user.idea_count, limit);

  return (
    <div className="mx-3 mt-2 mb-2 flex-none rounded-card bg-bd-sb-hover px-3 py-[11px]">
      <div className="flex items-center gap-2 text-[12px]">
        <span className="flex-1 font-semibold text-bd-sb-fg">
          {user.plan === "guest" ? "مهمان" : "کاربر عادی"}
        </span>
        <span className="text-bd-sb-fg-2">
          {toPersianDigits(used)} از {toPersianDigits(limit)} ایده
        </span>
      </div>
      <span className="mt-2 block h-1 overflow-hidden rounded-full bg-bd-sb-line">
        <span
          className="block h-1 rounded-full bg-bd-sb-fg transition-[width] duration-300"
          style={{ width: `${limit === 0 ? 0 : (used / limit) * 100}%` }}
        />
      </span>
      <div className="mt-2.5 flex items-center gap-1.5 text-[11.5px] text-bd-sb-fg-2">
        <CrownSimpleIcon size={12} weight="fill" className="flex-none" />
        ایدهٔ بیشتر، عکس و صدا برای کاربر ویژه
      </div>
    </div>
  );
}

/** «خرید اشتراک», at the foot of the sidebar; just the crown when it is collapsed. */
function SubscribeItem({ expanded, onClick }: { expanded: boolean; onClick: () => void }) {
  return (
    <div className="flex-none px-3 pt-1 pb-3.5">
      <button
        type="button"
        title="خرید اشتراک"
        onClick={onClick}
        className={`flex h-[38px] cursor-pointer items-center justify-center gap-2 rounded-[9px] border-0 bg-bd-sb-fg text-[13px] font-semibold whitespace-nowrap text-bd-sb-bg hover:opacity-90 ${
          expanded ? "w-full" : "w-[42px]"
        }`}
      >
        <CrownSimpleIcon size={17} weight="fill" className="flex-none" />
        {expanded ? "خرید اشتراک" : null}
      </button>
    </div>
  );
}

/**
 * The two concave corners that make the active item read as a tab cut out of
 * the sidebar. The sidebar sits on the right, so the tab meets the page on its
 * left edge, and the gradients are drawn in those physical directions.
 */
function TabCorners() {
  return (
    <>
      <span
        className="pointer-events-none absolute end-0 top-[-16px] size-4"
        style={{
          background:
            "radial-gradient(circle at top right, transparent 16px, var(--color-bd-bg) 16.5px)",
        }}
      />
      <span
        className="pointer-events-none absolute end-0 bottom-[-16px] size-4"
        style={{
          background:
            "radial-gradient(circle at bottom right, transparent 16px, var(--color-bd-bg) 16.5px)",
        }}
      />
    </>
  );
}

function MenuItem({
  icon,
  children,
  onClick,
  danger = false,
}: {
  icon: ReactNode;
  children: ReactNode;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-8 w-full cursor-pointer items-center gap-[9px] rounded-[7px] border-0 bg-transparent px-[9px] text-right text-[13px] hover:bg-bd-surface-3"
      style={{ color: danger ? "var(--color-bd-danger)" : "var(--color-bd-text)" }}
    >
      {icon}
      {children}
    </button>
  );
}
