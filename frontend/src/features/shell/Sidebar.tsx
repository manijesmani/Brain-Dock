import {
  ArchiveIcon,
  BellIcon,
  BrainIcon,
  DotsThreeIcon,
  GaugeIcon,
  GearIcon,
  LightbulbIcon,
  PaletteIcon,
  PencilSimpleIcon,
  PlusIcon,
  SidebarSimpleIcon,
  TrashIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { toPersianDigits } from "@/shared/lib/persian";
import type { Category } from "@/types/domain";

const EXPANDED_WIDTH = 312;
const COLLAPSED_WIDTH = 82;

const NAV = [
  { path: ROUTES.dashboard, label: "داشبورد", Icon: GaugeIcon },
  { path: ROUTES.ideas, label: "همهٔ ایده‌ها", Icon: LightbulbIcon },
  { path: ROUTES.archive, label: "آرشیو", Icon: ArchiveIcon },
  { path: ROUTES.notifications, label: "اعلان‌ها", Icon: BellIcon },
  { path: ROUTES.settings, label: "تنظیمات", Icon: GearIcon },
] as const;

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  categories: Category[];
  selectedCategory: number | null;
  onSelectCategory: (id: number | null) => void;
  unreadCount: number;
  onAddCategory: () => void;
  onEditCategory: (category: Category) => void;
  onDeleteCategory: (category: Category) => void;
}

export function Sidebar({
  collapsed,
  onToggleCollapse,
  categories,
  selectedCategory,
  onSelectCategory,
  unreadCount,
  onAddCategory,
  onEditCategory,
  onDeleteCategory,
}: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const expanded = !collapsed;
  const [openMenu, setOpenMenu] = useState<number | null>(null);

  const isActive = (path: string) =>
    path === ROUTES.ideas
      ? location.pathname === path && selectedCategory === null
      : location.pathname === path;

  return (
    <aside
      className="sticky top-0 flex h-screen flex-none flex-col overflow-hidden bg-bd-sb-bg text-bd-sb-fg transition-[width] duration-200"
      style={{
        width: expanded ? EXPANDED_WIDTH : COLLAPSED_WIDTH,
        transitionTimingFunction: "cubic-bezier(.4,0,.2,1)",
      }}
    >
      <div className="flex items-center gap-2.5 px-[16px] pt-[22.5px] pb-4">
        {/* With the sidebar collapsed the mark is also the way back out. */}
        <button
          type="button"
          title={expanded ? "BrainDock" : "باز کردن نوار"}
          onClick={() => {
            if (collapsed) onToggleCollapse();
          }}
          className={`grid size-[37.5px] flex-none place-items-center rounded-[11px] border-0 bg-bd-sb-fg p-0 text-bd-sb-bg ${
            collapsed ? "cursor-pointer" : "cursor-default"
          }`}
        >
          <BrainIcon size={22.5} />
        </button>
        {expanded ? (
          <>
            <span className="flex-1 font-wordmark text-[20.5px] font-bold tracking-tight whitespace-nowrap">
              BrainDock
            </span>
            <button
              type="button"
              onClick={onToggleCollapse}
              title="جمع کردن نوار"
              className="grid size-7 flex-none cursor-pointer place-items-center rounded-button border-0 bg-transparent text-bd-sb-fg-3 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
            >
              <SidebarSimpleIcon size={20} />
            </button>
          </>
        ) : null}
      </div>

      <nav className="flex flex-col gap-1 ps-2">
        {NAV.map(({ path, label, Icon }) => {
          const active = isActive(path);
          return (
            <button
              key={path}
              type="button"
              title={label}
              onClick={() => {
                if (path === ROUTES.ideas) onSelectCategory(null);
                void navigate(path);
              }}
              className={`relative flex h-[47.5px] cursor-pointer items-center gap-[14px] border-0 px-[14px] text-[17px] transition-colors ${
                active
                  ? "me-0 rounded-[0_24px_24px_0] bg-bd-bg font-semibold text-bd-accent"
                  : "me-2 rounded-[11px] bg-transparent text-bd-sb-fg-2 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
              }`}
            >
              {active ? <TabCorners /> : null}
              <Icon size={24} className="flex-none" />
              {expanded ? (
                <span className="flex-1 text-right whitespace-nowrap">{label}</span>
              ) : null}
              {path === ROUTES.notifications && unreadCount > 0 ? (
                <span
                  className={`grid h-[22.5px] min-w-[22.5px] flex-none place-items-center rounded-full px-[6px] text-[14px] font-semibold ${
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

      <div className="mx-3 mt-[17.5px] mb-3 h-px bg-bd-sb-line" />

      {/* The vertical padding, pulled back by the negative margin, leaves room
          for a selected category's tab corners inside the scrolling area. */}
      <div className="-mt-4 min-h-0 flex-1 overflow-y-auto py-4 ps-2">
        {expanded ? (
          <div className="px-[14px] pt-0.5 pb-2 text-[14.5px] font-semibold text-bd-sb-fg-3">
            دسته‌بندی‌ها
          </div>
        ) : null}

        {categories.map((category) => {
          // Only one tab at a time: a category is the tab while it is being
          // browsed, and "all ideas" then gives the tab up.
          const tab = selectedCategory === category.id && location.pathname === ROUTES.ideas;
          return (
            <div key={category.id} className={`relative mb-0.5 ${tab ? "me-0" : "me-2"}`}>
              <button
                type="button"
                title={category.name}
                onClick={() => {
                  onSelectCategory(category.id);
                  void navigate(ROUTES.ideas);
                }}
                className={`relative flex h-[42.5px] w-full cursor-pointer items-center gap-[14px] border-0 px-[14px] text-[16px] transition-colors ${
                  tab
                    ? "rounded-[0_21px_21px_0] bg-bd-bg font-semibold text-bd-accent"
                    : "rounded-button bg-transparent text-bd-sb-fg-2 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
                }`}
              >
                {tab ? <TabCorners /> : null}
                <span
                  className="size-2 flex-none rounded-full"
                  style={{
                    background: category.color,
                    boxShadow: tab
                      ? `0 0 0 4px ${category.color}22`
                      : "0 0 0 1.5px var(--color-bd-sb-fg)",
                  }}
                />
                {expanded ? (
                  <>
                    <span className="flex-1 overflow-hidden text-right text-ellipsis whitespace-nowrap">
                      {category.name}
                    </span>
                    <span
                      className={`flex-none pe-[27.5px] text-[14.5px] font-normal ${
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
                  className={`absolute end-1.5 top-1.5 grid size-[27.5px] cursor-pointer place-items-center rounded-[7.5px] border-0 bg-transparent ${
                    tab
                      ? "text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
                      : "text-bd-sb-fg-3 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
                  }`}
                >
                  <DotsThreeIcon size={20} />
                </button>
              ) : null}

              {openMenu === category.id ? (
                <>
                  <div className="fixed inset-0 z-[1200]" onClick={() => setOpenMenu(null)} />
                  <div
                    className="absolute end-1.5 top-8 z-[1300] min-w-[197.5px] rounded-card border border-bd-border-2 bg-bd-surface-2 p-[6px] shadow-bd-lg"
                    style={{ animation: "bd-pop 150ms ease-out" }}
                  >
                    <MenuItem
                      icon={<PencilSimpleIcon size={19} />}
                      onClick={() => {
                        setOpenMenu(null);
                        onEditCategory(category);
                      }}
                    >
                      ویرایش نام
                    </MenuItem>
                    <MenuItem
                      icon={<PaletteIcon size={19} />}
                      onClick={() => {
                        setOpenMenu(null);
                        onEditCategory(category);
                      }}
                    >
                      تغییر رنگ
                    </MenuItem>
                    <span className="mx-1 my-[6px] block h-px bg-bd-border" />
                    <MenuItem
                      icon={<TrashIcon size={19} />}
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
          className="mt-1 flex h-[42.5px] w-[calc(100%-10px)] cursor-pointer items-center gap-[14px] rounded-button border-0 bg-transparent px-[14px] text-[16px] text-bd-sb-fg-3 hover:bg-bd-sb-hover hover:text-bd-sb-fg"
        >
          <span className="grid w-2 flex-none place-items-center">
            <PlusIcon size={20} />
          </span>
          {expanded ? <span className="whitespace-nowrap">دستهٔ جدید</span> : null}
        </button>
      </div>
    </aside>
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
        className="pointer-events-none absolute end-0 top-[-20px] size-4"
        style={{
          background:
            "radial-gradient(circle at top right, transparent 20px, var(--color-bd-bg) 20.5px)",
        }}
      />
      <span
        className="pointer-events-none absolute end-0 bottom-[-20px] size-4"
        style={{
          background:
            "radial-gradient(circle at bottom right, transparent 20px, var(--color-bd-bg) 20.5px)",
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
      className="flex h-8 w-full cursor-pointer items-center gap-[11px] rounded-[9px] border-0 bg-transparent px-[11px] text-right text-[16px] hover:bg-bd-surface-3"
      style={{ color: danger ? "var(--color-bd-danger)" : "var(--color-bd-text)" }}
    >
      {icon}
      {children}
    </button>
  );
}
