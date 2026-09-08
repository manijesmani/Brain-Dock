import {
  ArchiveIcon,
  BellIcon,
  BrainIcon,
  CaretLeftIcon,
  CaretRightIcon,
  DotsThreeIcon,
  GaugeIcon,
  GearIcon,
  LightbulbIcon,
  MagnifyingGlassIcon,
  MoonIcon,
  PaletteIcon,
  PencilSimpleIcon,
  PlusIcon,
  SidebarSimpleIcon,
  SunIcon,
  TrashIcon,
} from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { toPersianDigits } from "@/shared/lib/persian";
import type { Theme } from "@/shared/hooks/useTheme";
import type { Category, CurrentUser } from "@/types/domain";

const EXPANDED_WIDTH = 250;
const COLLAPSED_WIDTH = 66;

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
  theme: Theme;
  onThemeChange: (theme: Theme) => void;
  user: CurrentUser;
  categories: Category[];
  selectedCategory: number | null;
  onSelectCategory: (id: number | null) => void;
  unreadCount: number;
  search: string;
  onSearchChange: (value: string) => void;
  onAddCategory: () => void;
  onEditCategory: (category: Category) => void;
  onDeleteCategory: (category: Category) => void;
}

export function Sidebar({
  collapsed,
  onToggleCollapse,
  theme,
  onThemeChange,
  user,
  categories,
  selectedCategory,
  onSelectCategory,
  unreadCount,
  search,
  onSearchChange,
  onAddCategory,
  onEditCategory,
  onDeleteCategory,
}: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const expanded = !collapsed;
  const [openMenu, setOpenMenu] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // The design puts a "/" hint on the search box; this is what honours it.
  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;

      if (event.key === "/" && !typing) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };

    document.addEventListener("keydown", focusSearch);
    return () => document.removeEventListener("keydown", focusSearch);
  }, []);

  const isActive = (path: string) =>
    path === ROUTES.ideas
      ? location.pathname === path && selectedCategory === null
      : location.pathname === path;

  return (
    <aside
      className="sticky top-0 flex h-screen flex-none flex-col overflow-hidden bg-bd-surface transition-[width] duration-200"
      style={{
        width: expanded ? EXPANDED_WIDTH : COLLAPSED_WIDTH,
        borderInlineEnd: "1px solid var(--color-bd-border)",
        transitionTimingFunction: "cubic-bezier(.4,0,.2,1)",
      }}
    >
      <div className="flex items-center gap-2.5 px-[13px] pt-4 pb-3">
        <div className="grid size-[30px] flex-none place-items-center rounded-[9px] bg-bd-accent text-bd-accent-ink">
          <BrainIcon size={18} />
        </div>
        {expanded ? (
          <>
            <span className="flex-1 font-wordmark text-[16.5px] font-bold tracking-tight whitespace-nowrap">
              BrainDock
            </span>
            <button
              type="button"
              onClick={onToggleCollapse}
              title="جمع کردن نوار"
              className="grid size-7 flex-none cursor-pointer place-items-center rounded-button border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
            >
              <SidebarSimpleIcon size={16} />
            </button>
          </>
        ) : null}
      </div>

      {expanded ? (
        <div className="px-3 pb-2.5">
          <div className="flex h-[34px] items-center gap-2 rounded-[9px] border border-bd-border bg-bd-surface-2 px-2.5">
            <MagnifyingGlassIcon size={15} className="flex-none text-bd-text-3" />
            <input
              ref={searchRef}
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              onFocus={() => void navigate(ROUTES.ideas)}
              placeholder="جستجو…"
              className="min-w-0 flex-1 border-0 bg-transparent text-[12.5px] text-bd-text outline-none"
            />
            <span
              title="میان‌بر جستجو"
              className="flex-none rounded-[5px] border border-bd-border-2 px-[7px] py-px font-mono text-[11px] text-bd-text-3"
            >
              /
            </span>
          </div>
        </div>
      ) : null}

      <nav className="flex flex-col gap-0.5 px-2">
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
              className="relative flex h-[38px] cursor-pointer items-center gap-[11px] rounded-[9px] border-0 px-[11px] text-[13.5px] transition-colors"
              style={{
                color: active ? "var(--color-bd-text)" : "var(--color-bd-text-2)",
                background: active ? "var(--color-bd-accent-soft)" : "transparent",
                fontWeight: active ? 600 : 400,
              }}
              onMouseEnter={(event) => {
                if (!active) event.currentTarget.style.background = "var(--color-bd-surface-2)";
              }}
              onMouseLeave={(event) => {
                if (!active) event.currentTarget.style.background = "transparent";
              }}
            >
              {active ? (
                <span
                  className="absolute top-[9px] bottom-[9px] w-[2.5px] rounded-full bg-bd-accent"
                  style={{ insetInlineEnd: 0 }}
                />
              ) : null}
              <Icon size={19} className="flex-none" />
              {expanded ? (
                <span className="flex-1 text-right whitespace-nowrap">{label}</span>
              ) : null}
              {path === ROUTES.notifications && unreadCount > 0 ? (
                <span className="grid h-[18px] min-w-[18px] flex-none place-items-center rounded-full bg-bd-accent px-[5px] text-[11px] font-semibold text-bd-accent-ink">
                  {toPersianDigits(unreadCount)}
                </span>
              ) : null}
            </button>
          );
        })}
      </nav>

      <div className="mx-3 my-2.5 h-px bg-bd-border" />

      <div className="min-h-0 flex-1 overflow-y-auto px-2">
        {expanded ? (
          <div className="px-[11px] pt-0.5 pb-2 text-[11.5px] font-semibold text-bd-text-3">
            دسته‌بندی‌ها
          </div>
        ) : null}

        {categories.map((category) => {
          const active = selectedCategory === category.id;
          return (
            <div key={category.id} className="relative">
              <button
                type="button"
                title={category.name}
                onClick={() => {
                  onSelectCategory(category.id);
                  void navigate(ROUTES.ideas);
                }}
                className="flex h-[34px] w-full cursor-pointer items-center gap-[11px] rounded-button border-0 px-[11px] text-[13px] transition-colors"
                style={{
                  color: active ? "var(--color-bd-text)" : "var(--color-bd-text-2)",
                  background: active ? "var(--color-bd-accent-soft)" : "transparent",
                }}
                onMouseEnter={(event) => {
                  if (!active) event.currentTarget.style.background = "var(--color-bd-surface-2)";
                }}
                onMouseLeave={(event) => {
                  if (!active) event.currentTarget.style.background = "transparent";
                }}
              >
                <span
                  className="size-2 flex-none rounded-full"
                  style={{
                    background: category.color,
                    boxShadow: `0 0 0 3px ${category.color}22`,
                  }}
                />
                {expanded ? (
                  <>
                    <span className="flex-1 overflow-hidden text-right text-ellipsis whitespace-nowrap">
                      {category.name}
                    </span>
                    <span className="flex-none pe-4 text-[11.5px] text-bd-text-3">
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
                  className="absolute top-1.5 grid size-[22px] cursor-pointer place-items-center rounded-md border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-3 hover:text-bd-text"
                  style={{ insetInlineStart: 8 }}
                >
                  <DotsThreeIcon size={16} />
                </button>
              ) : null}

              {openMenu === category.id ? (
                <>
                  <div className="fixed inset-0 z-[1200]" onClick={() => setOpenMenu(null)} />
                  <div
                    className="absolute top-8 z-[1300] min-w-[158px] rounded-card border border-bd-border-2 bg-bd-surface-2 p-[5px] shadow-bd-lg"
                    style={{ insetInlineStart: 6, animation: "bd-pop 150ms ease-out" }}
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
                    <span className="my-[5px] mx-1 block h-px bg-bd-border" />
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
          className="mt-1 flex h-[34px] w-full cursor-pointer items-center gap-[11px] rounded-button border-0 bg-transparent px-[11px] text-[13px] text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
        >
          <PlusIcon size={16} className="w-2 flex-none text-center" />
          {expanded ? <span className="whitespace-nowrap">دستهٔ جدید</span> : null}
        </button>
      </div>

      <div className="flex flex-col gap-2 border-t border-bd-border px-2 pt-2.5 pb-3">
        <div className="flex gap-[3px] rounded-[9px] bg-bd-surface-2 p-[3px]">
          <button
            type="button"
            onClick={() => onThemeChange("dark")}
            title="حالت شب"
            className="grid h-7 flex-1 cursor-pointer place-items-center rounded-[7px] border-0"
            style={{
              background: theme === "dark" ? "var(--color-bd-surface-3)" : "transparent",
              color: theme === "dark" ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
            }}
          >
            <MoonIcon size={15} />
          </button>
          {expanded ? (
            <button
              type="button"
              onClick={() => onThemeChange("light")}
              title="حالت روز"
              className="grid h-7 flex-1 cursor-pointer place-items-center rounded-[7px] border-0"
              style={{
                background: theme === "light" ? "var(--color-bd-surface-3)" : "transparent",
                color: theme === "light" ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
              }}
            >
              <SunIcon size={15} />
            </button>
          ) : null}
        </div>

        <button
          type="button"
          onClick={onToggleCollapse}
          title="حساب کاربری"
          className="flex cursor-pointer items-center gap-2.5 rounded-card bg-transparent p-[7px] text-bd-text hover:bg-bd-surface-2"
          style={{
            border: `1px solid ${expanded ? "var(--color-bd-border)" : "transparent"}`,
          }}
        >
          <span className="grid size-[30px] flex-none place-items-center rounded-full bg-bd-surface-3 text-[12.5px] font-semibold text-bd-text-2">
            {user.display_name.charAt(0)}
          </span>
          {expanded ? (
            <span className="min-w-0 flex-1 text-right">
              <span className="block text-[13px] font-medium whitespace-nowrap">
                {user.display_name}
              </span>
              <span
                dir="ltr"
                className="block overflow-hidden text-[11px] text-ellipsis whitespace-nowrap text-bd-text-3"
              >
                {user.email}
              </span>
            </span>
          ) : null}
          {expanded ? (
            <CaretRightIcon size={14} className="flex-none text-bd-text-3" />
          ) : (
            <CaretLeftIcon size={14} className="flex-none text-bd-text-3" />
          )}
        </button>
      </div>
    </aside>
  );
}

function MenuItem({
  icon,
  children,
  onClick,
  danger = false,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
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
