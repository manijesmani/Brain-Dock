import {
  LinkIcon,
  MinusIcon,
  MoonIcon,
  PencilSimpleIcon,
  PlusIcon,
  SignOutIcon,
  SunIcon,
  TrashIcon,
} from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { PageHeader } from "@/features/shell/PageHeader";
import { useApp } from "@/features/shell/appContext";
import {
  useCreateTelegramLink,
  useDeleteCategory,
  useDisconnectTelegram,
  useLogout,
  useTelegramLink,
  useUpdateProfile,
} from "@/shared/api/queries";
import { toPersianDigits } from "@/shared/lib/persian";
import type { ReactNode } from "react";

/** The stepper's bounds, matching the validators on the user model. */
const STALE_MIN = 1;
const STALE_MAX = 90;

export function SettingsPage() {
  const navigate = useNavigate();
  // The theme comes from the shell, so this page and the account menu always
  // agree on it.
  const { user, categories, openCategoryDialog, theme, setTheme } = useApp();

  const { data: telegram } = useTelegramLink();
  const createLink = useCreateTelegramLink();
  const disconnect = useDisconnectTelegram();
  const updateProfile = useUpdateProfile();
  const deleteCategory = useDeleteCategory();
  const logout = useLogout();

  const linked = telegram?.is_linked ?? false;

  const setStale = (value: number) => {
    const clamped = Math.min(STALE_MAX, Math.max(STALE_MIN, value));
    if (clamped !== user.stale_after_days) {
      updateProfile.mutate({ stale_after_days: clamped });
    }
  };

  return (
    <main className="min-w-0 flex-1 px-[47.5px] pt-[32.5px] pb-[137.5px]">
      <PageHeader title="تنظیمات" />

      <div className="flex max-w-[925px] flex-col gap-4">
        <Section>
          <div className="mb-1.5 flex items-center gap-2.5">
            <h2 className="m-0 text-[19px] font-semibold">اتصال ربات تلگرام</h2>
            <span
              className="inline-flex items-center gap-1.5 text-[15.5px]"
              style={{
                color: linked ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
              }}
            >
              <span
                className="size-[9px] rounded-full"
                style={{
                  background: linked ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
                }}
              />
              {linked ? "متصل" : "متصل نیست"}
            </span>
          </div>
          <p className="m-0 mb-[19px] text-[16px] leading-[1.8] text-bd-text-2">
            ایده‌ها را در تلگرام بفرست تا مستقیم در BrainDock ثبت شوند.
          </p>

          {telegram?.link ? (
            <div className="mb-[16px] flex items-center gap-2.5 rounded-[11px] border border-bd-border bg-bd-surface-2 px-3.5 py-[14px]">
              <LinkIcon size={20} className="text-bd-text-3" />
              <span dir="ltr" className="flex-1 font-mono text-[15.5px] text-bd-text">
                {telegram.link}
              </span>
              <span className="text-[14.5px] text-bd-text-3">یک‌بارمصرف</span>
            </div>
          ) : null}

          <div className="flex gap-[11px]">
            {linked ? (
              <button
                type="button"
                onClick={() => disconnect.mutate()}
                className="h-[47.5px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[19px] text-[16px] text-bd-danger hover:bg-bd-surface-2"
              >
                قطع اتصال
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => createLink.mutate()}
              disabled={createLink.isPending}
              className="h-[47.5px] cursor-pointer rounded-button border-0 bg-bd-accent px-[19px] text-[16px] font-medium text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
            >
              ساخت لینک اتصال
            </button>
          </div>
        </Section>

        <Section>
          <div className="mb-3.5 flex items-center">
            <h2 className="m-0 flex-1 text-[19px] font-semibold">مدیریت دسته‌بندی‌ها</h2>
            <button
              type="button"
              onClick={() => openCategoryDialog()}
              className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-button border border-bd-border-2 bg-transparent px-3 text-[15.5px] text-bd-text hover:bg-bd-surface-2"
            >
              <PlusIcon size={17.5} />
              دستهٔ جدید
            </button>
          </div>

          <div className="overflow-hidden rounded-[11px] border border-bd-border">
            {categories.length === 0 ? (
              <div className="px-3.5 py-6 text-center text-[16px] text-bd-text-3">
                هنوز دسته‌ای نساخته‌ای
              </div>
            ) : (
              categories.map((category, index) => (
                <div
                  key={category.id}
                  className="flex items-center gap-[14px] px-3.5 py-[14px]"
                  style={{
                    borderTop: index === 0 ? "0" : "1px solid var(--color-bd-border)",
                  }}
                >
                  <span
                    className="size-[11px] flex-none rounded-full"
                    style={{ background: category.color }}
                  />
                  <span className="flex-1 text-[17px]">{category.name}</span>
                  <span className="text-[15px] text-bd-text-3">
                    {toPersianDigits(category.idea_count)} ایده
                  </span>
                  <button
                    type="button"
                    title="ویرایش"
                    onClick={() => openCategoryDialog(category)}
                    className="grid size-[37.5px] cursor-pointer place-items-center rounded-[9px] border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
                  >
                    <PencilSimpleIcon size={19} />
                  </button>
                  <button
                    type="button"
                    title="حذف"
                    onClick={() => deleteCategory.mutate(category.id)}
                    className="grid size-[37.5px] cursor-pointer place-items-center rounded-[9px] border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-danger"
                  >
                    <TrashIcon size={19} />
                  </button>
                </div>
              ))
            )}
          </div>
        </Section>

        <Section>
          <h2 className="m-0 mb-1.5 text-[19px] font-semibold">تعریف ایدهٔ راکد</h2>
          <p className="m-0 mb-[19px] text-[16px] leading-[1.8] text-bd-text-2">
            بعد از چند روز بدون تغییر، ایده راکد شمرده شود.
          </p>
          <div className="inline-flex items-center gap-0.5 rounded-[11px] border border-bd-border-2 p-[4px]">
            <button
              type="button"
              onClick={() => setStale(user.stale_after_days - 1)}
              disabled={user.stale_after_days <= STALE_MIN}
              className="grid size-8 cursor-pointer place-items-center rounded-[9px] border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text disabled:cursor-not-allowed disabled:opacity-40"
            >
              <MinusIcon size={17.5} />
            </button>
            <span className="min-w-[90px] text-center text-[17.5px] font-semibold">
              {toPersianDigits(user.stale_after_days)} روز
            </span>
            <button
              type="button"
              onClick={() => setStale(user.stale_after_days + 1)}
              disabled={user.stale_after_days >= STALE_MAX}
              className="grid size-8 cursor-pointer place-items-center rounded-[9px] border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text disabled:cursor-not-allowed disabled:opacity-40"
            >
              <PlusIcon size={17.5} />
            </button>
          </div>
        </Section>

        <Section>
          <h2 className="m-0 mb-3.5 text-[19px] font-semibold">حالت نمایش</h2>
          <div className="inline-flex gap-[4px] rounded-[11px] bg-bd-surface-2 p-[4px]">
            <ThemeButton active={theme === "dark"} onClick={() => setTheme("dark")}>
              <MoonIcon size={19} />
              شب
            </ThemeButton>
            <ThemeButton active={theme === "light"} onClick={() => setTheme("light")}>
              <SunIcon size={19} />
              روز
            </ThemeButton>
          </div>
        </Section>

        <section className="flex items-center gap-3.5 rounded-card border border-bd-border bg-bd-surface px-[27.5px] py-[22.5px] shadow-bd">
          <div className="flex-1">
            <div className="text-[17.5px] font-semibold">خروج از حساب</div>
            <div className="mt-0.5 text-[15.5px] text-bd-text-2">
              {user.display_name} · حساب شخصی
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              void (async () => {
                await logout.mutateAsync();
                void navigate(ROUTES.login, { replace: true });
              })();
            }}
            className="inline-flex h-[47.5px] cursor-pointer items-center gap-[9px] rounded-button border border-bd-border-2 bg-transparent px-[19px] text-[16px] text-bd-danger hover:bg-bd-surface-2"
          >
            <SignOutIcon size={20} />
            خروج
          </button>
        </section>
      </div>
    </main>
  );
}

function Section({ children }: { children: ReactNode }) {
  return (
    <section className="rounded-card border border-bd-border bg-bd-surface px-[27.5px] py-5 shadow-bd">
      {children}
    </section>
  );
}

function ThemeButton({
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
      className="inline-flex h-[42.5px] cursor-pointer items-center gap-2 rounded-[9px] border-0 px-4 text-[16px]"
      style={{
        background: active ? "var(--color-bd-surface-3)" : "transparent",
        color: active ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
      }}
    >
      {children}
    </button>
  );
}
