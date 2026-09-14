import {
  BellIcon,
  CaretDownIcon,
  GearIcon,
  MagnifyingGlassIcon,
  MoonIcon,
  SignOutIcon,
  SunIcon,
  XIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { useApp } from "@/features/shell/appContext";
import { useLogout } from "@/shared/api/queries";
import { toPersianDigits } from "@/shared/lib/persian";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** A category's colour, shown before the title while browsing it. */
  dot?: string | null;
  /** The dashboard greets with a larger title than the other screens. */
  large?: boolean;
}

/**
 * The top bar every screen but the note editor shares: the page's title on
 * the start side, then search, notifications and the account menu.
 */
export function PageHeader({ title, subtitle, dot, large = false }: PageHeaderProps) {
  return (
    <header className="mb-6 flex min-h-[65px] items-center gap-2.5">
      {dot ? (
        <span className="size-2.5 flex-none rounded-full" style={{ background: dot }} />
      ) : null}

      <div className="min-w-0 flex-1">
        <h1
          className={`m-0 leading-[1.35] font-bold tracking-tight ${
            large ? "text-[32.5px]" : "text-[27.5px]"
          }`}
        >
          {title}
        </h1>
        {subtitle ? <div className="mt-[4px] text-[16px] text-bd-text-3">{subtitle}</div> : null}
      </div>

      <HeaderSearch />
      <NotificationBell />
      <AccountMenu />
    </header>
  );
}

function HeaderSearch() {
  const navigate = useNavigate();
  const location = useLocation();
  const { search, setSearch, searchOpen, setSearchOpen } = useApp();
  const inputRef = useRef<HTMLInputElement>(null);

  const open = searchOpen || search !== "";

  // The design puts a "/" hint on the field; this is what honours it.
  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;

      if (event.key === "/" && !typing) {
        event.preventDefault();
        setSearchOpen(true);
        inputRef.current?.focus();
      }
    };

    document.addEventListener("keydown", focusSearch);
    return () => document.removeEventListener("keydown", focusSearch);
  }, [setSearchOpen]);

  if (!open) {
    return (
      <button
        type="button"
        title="جستجو"
        onClick={() => setSearchOpen(true)}
        className="grid size-[47.5px] flex-none cursor-pointer place-items-center rounded-full border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text"
      >
        <MagnifyingGlassIcon size={22.5} />
      </button>
    );
  }

  return (
    <div
      className="flex h-[47.5px] w-[325px] flex-none items-center gap-2 rounded-full border border-bd-accent bg-bd-surface px-3"
      style={{
        boxShadow: "0 0 0 4px var(--color-bd-accent-soft)",
        animation: "bd-pop 150ms ease-out",
      }}
    >
      <MagnifyingGlassIcon size={20} className="flex-none text-bd-text-3" />
      <input
        ref={inputRef}
        autoFocus
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        onFocus={() => {
          // Search is over ideas, so typing anywhere else takes you to them.
          if (location.pathname !== ROUTES.ideas && location.pathname !== ROUTES.archive) {
            void navigate(ROUTES.ideas);
          }
        }}
        onBlur={() => {
          if (search === "") setSearchOpen(false);
        }}
        placeholder="جستجو در ایده‌ها…"
        className="min-w-0 flex-1 border-0 bg-transparent text-[16px] text-bd-text outline-none"
      />
      <span
        title="میان‌بر جستجو"
        className="flex-none rounded-[6px] border border-bd-border-2 px-1.5 font-mono text-[14px] text-bd-text-3"
      >
        /
      </span>
      <button
        type="button"
        title="بستن جستجو"
        onClick={() => {
          setSearch("");
          setSearchOpen(false);
        }}
        className="grid size-[27.5px] flex-none cursor-pointer place-items-center rounded-full border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
      >
        <XIcon size={16} />
      </button>
    </div>
  );
}

function NotificationBell() {
  const navigate = useNavigate();
  const { unreadCount } = useApp();

  return (
    <button
      type="button"
      title="اعلان‌ها"
      onClick={() => void navigate(ROUTES.notifications)}
      className="relative grid size-[47.5px] flex-none cursor-pointer place-items-center rounded-full border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text"
    >
      <BellIcon size={22.5} />
      {unreadCount > 0 ? (
        <span
          className="absolute top-1 grid h-4 min-w-4 place-items-center rounded-full bg-bd-accent px-1 text-[12.5px] leading-none font-semibold text-bd-accent-ink"
          style={{ insetInlineEnd: "4px", boxShadow: "0 0 0 2.5px var(--color-bd-bg)" }}
        >
          {toPersianDigits(unreadCount)}
        </span>
      ) : null}
    </button>
  );
}

function AccountMenu() {
  const navigate = useNavigate();
  const { user, theme, setTheme } = useApp();
  const logout = useLogout();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;

    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open]);

  const initial = user.display_name.charAt(0);

  return (
    <div className="relative flex-none">
      <button
        type="button"
        title="حساب کاربری"
        onClick={() => setOpen((current) => !current)}
        className={`inline-flex h-[47.5px] cursor-pointer items-center gap-1.5 rounded-full border-0 ps-[4px] pe-2 text-bd-text-3 ${
          open ? "bg-bd-surface-2" : "bg-transparent hover:bg-bd-surface-2"
        }`}
      >
        <span className="grid size-8 place-items-center rounded-full bg-bd-accent-soft text-[16px] font-semibold text-bd-accent">
          {initial}
        </span>
        <CaretDownIcon size={15} />
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-[1200]" onClick={() => setOpen(false)} />
          <div
            className="absolute top-[57.5px] z-[1300] w-[290px] rounded-card border border-bd-border-2 bg-bd-surface-2 p-[6px] shadow-bd-lg"
            style={{ insetInlineEnd: 0, animation: "bd-pop 150ms ease-out" }}
          >
            <div className="flex items-center gap-2.5 px-[11px] pt-2 pb-[14px]">
              <span className="grid size-[42.5px] flex-none place-items-center rounded-full bg-bd-accent-soft text-[17px] font-semibold text-bd-accent">
                {initial}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[17px] font-semibold">{user.display_name}</span>
                <span
                  dir="ltr"
                  className="block overflow-hidden text-right text-[14.5px] text-ellipsis whitespace-nowrap text-bd-text-3"
                >
                  {user.email}
                </span>
              </span>
            </div>

            <div className="mx-1 mb-1.5 flex gap-[4px] rounded-[11px] bg-bd-bg p-[4px]">
              <ThemeOption active={theme === "dark"} onClick={() => setTheme("dark")}>
                <MoonIcon size={17.5} />
                شب
              </ThemeOption>
              <ThemeOption active={theme === "light"} onClick={() => setTheme("light")}>
                <SunIcon size={17.5} />
                روز
              </ThemeOption>
            </div>

            <span className="mx-1 mb-[6px] block h-px bg-bd-border" />

            <MenuButton
              icon={<GearIcon size={19} />}
              onClick={() => {
                setOpen(false);
                void navigate(ROUTES.settings);
              }}
            >
              تنظیمات
            </MenuButton>
            <MenuButton
              danger
              icon={<SignOutIcon size={19} />}
              onClick={() => {
                void (async () => {
                  await logout.mutateAsync();
                  void navigate(ROUTES.login, { replace: true });
                })();
              }}
            >
              خروج
            </MenuButton>
          </div>
        </>
      ) : null}
    </div>
  );
}

function ThemeOption({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-[37.5px] flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-[9px] border-0 text-[15.5px]"
      style={{
        background: active ? "var(--color-bd-surface-3)" : "transparent",
        color: active ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
      }}
    >
      {children}
    </button>
  );
}

function MenuButton({
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
