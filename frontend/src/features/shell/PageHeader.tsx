import {
  BellIcon,
  CaretDownIcon,
  CrownSimpleIcon,
  GearIcon,
  ListIcon,
  MagnifyingGlassIcon,
  MoonIcon,
  SignInIcon,
  SignOutIcon,
  SunIcon,
  UserPlusIcon,
  XIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { PLAN_LABELS } from "@/features/plans/labels";
import { useApp } from "@/features/shell/appContext";
import { useLogout } from "@/shared/api/queries";
import { toPersianDigits } from "@/shared/lib/persian";
import { Avatar } from "@/shared/ui/Avatar";
import type { Plan } from "@/types/domain";

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
  const { openNav } = useApp();

  // It wraps only to give an open search field a line of its own on a phone;
  // every other item has a fixed size, and the title gives way before any of
  // them.
  return (
    <header className="mb-4 flex min-h-[52px] flex-wrap items-center gap-x-1 gap-y-3 sm:gap-x-2.5 lg:mb-6">
      <button
        type="button"
        title="منو"
        onClick={openNav}
        className="-ms-2 grid size-10 flex-none cursor-pointer place-items-center rounded-full border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text lg:hidden"
      >
        <ListIcon size={19} />
      </button>

      {dot ? (
        <span className="size-2.5 flex-none rounded-full" style={{ background: dot }} />
      ) : null}

      <div className="min-w-0 flex-1">
        <h1
          className={`m-0 leading-[1.35] font-bold tracking-tight ${
            large ? "text-[21px] sm:text-[26px]" : "text-[18.5px] sm:text-[22px]"
          }`}
        >
          {title}
        </h1>
        {subtitle ? (
          <div className="mt-[3px] text-[11.5px] text-bd-text-3 sm:text-[13px]">{subtitle}</div>
        ) : null}
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
        className="grid size-10 flex-none cursor-pointer place-items-center rounded-full border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text sm:size-[38px]"
      >
        <MagnifyingGlassIcon size={18} />
      </button>
    );
  }

  // On a phone the open field takes a line of its own under the header.
  return (
    <div
      className="order-last flex h-11 w-full flex-none items-center gap-2 rounded-full border border-bd-accent bg-bd-surface px-3 sm:order-none sm:h-[38px] sm:w-[260px]"
      style={{
        boxShadow: "0 0 0 3px var(--color-bd-accent-soft)",
        animation: "bd-pop 150ms ease-out",
      }}
    >
      <MagnifyingGlassIcon size={16} className="flex-none text-bd-text-3" />
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
        className="min-w-0 flex-1 border-0 bg-transparent text-[13px] text-bd-text outline-none"
      />
      {/* A keyboard shortcut, so only where there is likely a keyboard. */}
      <span
        title="میان‌بر جستجو"
        className="hidden flex-none rounded-[5px] border border-bd-border-2 px-1.5 font-mono text-[11px] text-bd-text-3 lg:block"
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
        className="grid size-[22px] flex-none cursor-pointer place-items-center rounded-full border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
      >
        <XIcon size={13} />
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
      className="relative grid size-10 flex-none cursor-pointer place-items-center rounded-full border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text sm:size-[38px]"
    >
      <BellIcon size={18} />
      {unreadCount > 0 ? (
        <span
          className="absolute top-1 grid h-4 min-w-4 place-items-center rounded-full bg-bd-accent px-1 text-[10px] leading-none font-semibold text-bd-accent-ink"
          style={{ insetInlineEnd: "3px", boxShadow: "0 0 0 2px var(--color-bd-bg)" }}
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
  const guest = user.plan === "guest";

  const goTo = (path: string) => {
    setOpen(false);
    void navigate(path);
  };

  useEffect(() => {
    if (!open) return;

    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open]);

  return (
    <div className="relative flex-none">
      <button
        type="button"
        title="حساب کاربری"
        onClick={() => setOpen((current) => !current)}
        className={`inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-full border-0 px-[3px] text-bd-text-3 sm:h-[38px] sm:pe-2 ${
          open ? "bg-bd-surface-2" : "bg-transparent hover:bg-bd-surface-2"
        }`}
      >
        <Avatar user={user} className="size-8 text-[13px]" />
        <CaretDownIcon size={12} className="hidden sm:block" />
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-[1200]" onClick={() => setOpen(false)} />
          <div
            className="absolute top-[46px] z-[1300] w-[232px] rounded-card border border-bd-border-2 bg-bd-surface-2 p-[5px] shadow-bd-lg"
            style={{ insetInlineEnd: 0, animation: "bd-pop 150ms ease-out" }}
          >
            <div className="flex items-center gap-2.5 px-[9px] pt-2 pb-[11px]">
              <Avatar user={user} className="size-[34px] text-[13.5px]" />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                  <span className="min-w-0 overflow-hidden text-[13.5px] font-semibold text-ellipsis whitespace-nowrap">
                    {user.display_name}
                  </span>
                  {guest ? null : <PlanChip plan={user.plan} />}
                </span>
                {guest ? (
                  <span className="block text-[11.5px] text-bd-text-3">
                    بدون حساب، فقط در همین مرورگر
                  </span>
                ) : (
                  <span
                    dir="ltr"
                    className="block overflow-hidden text-right text-[11.5px] text-ellipsis whitespace-nowrap text-bd-text-3"
                  >
                    {user.email}
                  </span>
                )}
              </span>
            </div>

            <div className="mx-1 mb-1.5 flex gap-[3px] rounded-[9px] bg-bd-bg p-[3px]">
              <ThemeOption active={theme === "dark"} onClick={() => setTheme("dark")}>
                <MoonIcon size={14} />
                شب
              </ThemeOption>
              <ThemeOption active={theme === "light"} onClick={() => setTheme("light")}>
                <SunIcon size={14} />
                روز
              </ThemeOption>
            </div>

            <span className="mx-1 mb-[5px] block h-px bg-bd-border" />

            {/* A guest has nothing to sign out of: leaving would only lose
                the guest account for good. */}
            {guest ? (
              <>
                <MenuButton icon={<UserPlusIcon size={15} />} onClick={() => goTo(ROUTES.signup)}>
                  ساخت حساب
                </MenuButton>
                <MenuButton icon={<SignInIcon size={15} />} onClick={() => goTo(ROUTES.login)}>
                  ورود به حساب
                </MenuButton>
              </>
            ) : null}
            <MenuButton icon={<GearIcon size={15} />} onClick={() => goTo(ROUTES.settings)}>
              تنظیمات
            </MenuButton>
            {guest ? null : (
              <MenuButton
                danger
                icon={<SignOutIcon size={15} />}
                onClick={() => {
                  void (async () => {
                    await logout.mutateAsync();
                    void navigate(ROUTES.login, { replace: true });
                  })();
                }}
              >
                خروج
              </MenuButton>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

/** The account's kind beside its name; premium and the owner in the crown's colour. */
function PlanChip({ plan }: { plan: Plan }) {
  const raised = plan === "premium" || plan === "owner";

  return (
    <span
      className="inline-flex flex-none items-center gap-1 rounded-full px-[7px] py-px text-[10.5px] font-semibold"
      style={{
        background: raised ? "var(--color-bd-warn-bg)" : "var(--color-bd-surface-3)",
        color: raised ? "var(--color-bd-warn)" : "var(--color-bd-text-2)",
      }}
    >
      {plan === "premium" ? <CrownSimpleIcon size={10} weight="fill" /> : null}
      {PLAN_LABELS[plan]}
    </span>
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
      className="inline-flex h-[30px] flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-[7px] border-0 text-[12.5px]"
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
      className="flex h-8 w-full cursor-pointer items-center gap-[9px] rounded-[7px] border-0 bg-transparent px-[9px] text-right text-[13px] hover:bg-bd-surface-3"
      style={{ color: danger ? "var(--color-bd-danger)" : "var(--color-bd-text)" }}
    >
      {icon}
      {children}
    </button>
  );
}
