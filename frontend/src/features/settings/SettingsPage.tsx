import {
  ImageIcon,
  LinkIcon,
  MinusIcon,
  MoonIcon,
  PencilSimpleIcon,
  PlusIcon,
  SignOutIcon,
  SunIcon,
  TrashIcon,
  UsersThreeIcon,
} from "@phosphor-icons/react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { UserPanelDialog } from "@/features/panel/UserPanelDialog";
import { DevicesSection } from "@/features/settings/DevicesSection";
import { PLAN_LABELS } from "@/features/plans/labels";
import { PageHeader } from "@/features/shell/PageHeader";
import { PageMain } from "@/features/shell/PageMain";
import { useApp } from "@/features/shell/appContext";
import {
  useCreateTelegramLink,
  useDeleteCategory,
  useDisconnectTelegram,
  useRemoveAvatar,
  useLogout,
  useTelegramLink,
  useUpdateProfile,
  useSite,
  useUploadAvatar,
} from "@/shared/api/queries";
import { errorMessage } from "@/shared/api/errors";
import { useToast } from "@/shared/hooks/useToast";
import { toPersianDigits } from "@/shared/lib/persian";
import { checkUpload, describeUpload } from "@/shared/lib/uploads";
import { Avatar } from "@/shared/ui/Avatar";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import type { ReactNode } from "react";

/** The stepper's bounds, matching the validators on the user model. */
const STALE_MIN = 1;
const STALE_MAX = 90;

export function SettingsPage() {
  const navigate = useNavigate();
  // The theme comes from the shell, so this page and the account menu always
  // agree on it.
  const { user, categories, openCategoryDialog, theme, setTheme } = useApp();

  const updateProfile = useUpdateProfile();
  const deleteCategory = useDeleteCategory();
  const logout = useLogout();
  const toast = useToast();
  const guest = user.plan === "guest";
  // Each section says for itself when something in it failed.
  const [staleError, setStaleError] = useState<string | null>(null);
  const [categoryError, setCategoryError] = useState<string | null>(null);

  const setStale = (value: number) => {
    const clamped = Math.min(STALE_MAX, Math.max(STALE_MIN, value));
    if (clamped !== user.stale_after_days) {
      setStaleError(null);
      updateProfile.mutate(
        { stale_after_days: clamped },
        {
          // One toast for a run of clicks on the stepper, not one per click.
          onSuccess: () => toast.show("تنظیمات ذخیره شد", { key: "settings" }),
          onError: (caught) =>
            setStaleError(errorMessage(caught, "ذخیرهٔ تنظیمات ناموفق بود. دوباره امتحان کن.")),
        },
      );
    }
  };

  const removeCategory = (id: number) => {
    setCategoryError(null);
    deleteCategory.mutate(id, {
      onSuccess: () => toast.show("دسته حذف شد"),
      onError: (caught) =>
        setCategoryError(errorMessage(caught, "حذف دسته ناموفق بود. دوباره امتحان کن.")),
    });
  };

  return (
    <PageMain>
      <PageHeader title="تنظیمات" />

      <div className="flex max-w-[740px] flex-col gap-4">
        {guest ? <GuestAccount /> : null}

        {/* The bot serves the site's owner alone, so nobody else sees it at
            all. The profile picture sits at the foot of its card, and has a
            card of its own for everyone else -- a guest has no profile. */}
        {user.can_use_telegram ? (
          <TelegramSection />
        ) : guest ? null : (
          <Section>
            <ProfilePicture standalone />
          </Section>
        )}

        {/* The owner's other exclusive feature; not rendered for anyone else. */}
        {user.can_manage_users ? <UserPanelSection /> : null}

        <Section>
          <div className="mb-3.5 flex items-center">
            <h2 className="m-0 flex-1 text-[15px] font-semibold">مدیریت دسته‌بندی‌ها</h2>
            <button
              type="button"
              onClick={() => openCategoryDialog()}
              className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-button border border-bd-border-2 bg-transparent px-3 text-[12.5px] text-bd-text hover:bg-bd-surface-2"
            >
              <PlusIcon size={14} />
              دستهٔ جدید
            </button>
          </div>

          <div className="overflow-hidden rounded-[9px] border border-bd-border">
            {categories.length === 0 ? (
              <div className="px-3.5 py-6 text-center text-[13px] text-bd-text-3">
                هنوز دسته‌ای نساخته‌ای
              </div>
            ) : (
              categories.map((category, index) => (
                <div
                  key={category.id}
                  className="flex items-center gap-[11px] px-3.5 py-[11px]"
                  style={{
                    borderTop: index === 0 ? "0" : "1px solid var(--color-bd-border)",
                  }}
                >
                  <span
                    className="size-[9px] flex-none rounded-full"
                    style={{ background: category.color }}
                  />
                  <span className="flex-1 text-[13.5px]">{category.name}</span>
                  <span className="text-[12px] text-bd-text-3">
                    {toPersianDigits(category.idea_count)} ایده
                  </span>
                  <button
                    type="button"
                    title="ویرایش"
                    onClick={() => openCategoryDialog(category)}
                    className="grid size-[30px] cursor-pointer place-items-center rounded-[7px] border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
                  >
                    <PencilSimpleIcon size={15} />
                  </button>
                  <button
                    type="button"
                    title="حذف"
                    onClick={() => removeCategory(category.id)}
                    className="grid size-[30px] cursor-pointer place-items-center rounded-[7px] border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-danger"
                  >
                    <TrashIcon size={15} />
                  </button>
                </div>
              ))
            )}
          </div>
          {categoryError ? <InlineAlert className="mt-3">{categoryError}</InlineAlert> : null}
        </Section>

        <Section>
          <h2 className="m-0 mb-1.5 text-[15px] font-semibold">تعریف ایدهٔ راکد</h2>
          <p className="m-0 mb-[15px] text-[13px] leading-[1.8] text-bd-text-2">
            بعد از چند روز بدون تغییر، ایده راکد شمرده شود.
          </p>
          <div className="inline-flex items-center gap-0.5 rounded-[9px] border border-bd-border-2 p-[3px]">
            <button
              type="button"
              onClick={() => setStale(user.stale_after_days - 1)}
              disabled={user.stale_after_days <= STALE_MIN}
              className="grid size-8 cursor-pointer place-items-center rounded-[7px] border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text disabled:cursor-not-allowed disabled:opacity-40"
            >
              <MinusIcon size={14} />
            </button>
            <span className="min-w-[72px] text-center text-[14px] font-semibold">
              {toPersianDigits(user.stale_after_days)} روز
            </span>
            <button
              type="button"
              onClick={() => setStale(user.stale_after_days + 1)}
              disabled={user.stale_after_days >= STALE_MAX}
              className="grid size-8 cursor-pointer place-items-center rounded-[7px] border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text disabled:cursor-not-allowed disabled:opacity-40"
            >
              <PlusIcon size={14} />
            </button>
          </div>
          {staleError ? <InlineAlert className="mt-3">{staleError}</InlineAlert> : null}
        </Section>

        <Section>
          <h2 className="m-0 mb-3.5 text-[15px] font-semibold">حالت نمایش</h2>
          <div className="inline-flex gap-[3px] rounded-[9px] bg-bd-surface-2 p-[3px]">
            <ThemeButton active={theme === "dark"} onClick={() => setTheme("dark")}>
              <MoonIcon size={15} />
              شب
            </ThemeButton>
            <ThemeButton active={theme === "light"} onClick={() => setTheme("light")}>
              <SunIcon size={15} />
              روز
            </ThemeButton>
          </div>
        </Section>

        {/* A guest has one browser and no password, so nothing to sign out of. */}
        {guest ? null : (
          <Section>
            <DevicesSection />
          </Section>
        )}

        {guest ? null : (
          <section className="flex items-center gap-3.5 rounded-card border border-bd-border bg-bd-surface px-4 py-[18px] shadow-bd sm:px-[22px]">
            <div className="flex-1">
              <div className="text-[14px] font-semibold">خروج از حساب</div>
              <div className="mt-0.5 text-[12.5px] text-bd-text-2">
                {user.display_name} · حساب {PLAN_LABELS[user.plan]}
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
              className="inline-flex h-[38px] cursor-pointer items-center gap-[7px] rounded-button border border-bd-border-2 bg-transparent px-[15px] text-[13px] text-bd-danger hover:bg-bd-surface-2"
            >
              <SignOutIcon size={16} />
              خروج
            </button>
          </section>
        )}
      </div>
    </PageMain>
  );
}

/** Linking the Telegram bot: the owner's alone. */
function TelegramSection() {
  const { data: telegram } = useTelegramLink();
  const createLink = useCreateTelegramLink();
  const disconnect = useDisconnectTelegram();
  const toast = useToast();

  const linked = telegram?.is_linked ?? false;
  const failure = createLink.error ?? disconnect.error;

  return (
    <Section>
      <div className="mb-1.5 flex items-center gap-2.5">
        <h2 className="m-0 text-[15px] font-semibold">اتصال ربات تلگرام</h2>
        <span
          className="inline-flex items-center gap-1.5 text-[12.5px]"
          style={{
            color: linked ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
          }}
        >
          <span
            className="size-[7px] rounded-full"
            style={{
              background: linked ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
            }}
          />
          {linked ? "متصل" : "متصل نیست"}
        </span>
      </div>
      <p className="m-0 mb-[15px] text-[13px] leading-[1.8] text-bd-text-2">
        ایده‌ها را در تلگرام بفرست تا مستقیم در BrainDock ثبت شوند.
      </p>

      {/* A link, so one tap opens the bot -- in the Telegram app on a
          phone. Long, so it wraps rather than running off a narrow screen. */}
      {telegram?.link ? (
        <a
          // The API sends the address as the design shows it, without a
          // scheme; as an href that would be read as a path on this site.
          href={telegram.link.includes("://") ? telegram.link : `https://${telegram.link}`}
          target="_blank"
          rel="noreferrer"
          title="باز کردن در تلگرام"
          className="mb-[13px] flex items-center gap-2.5 rounded-[9px] border border-bd-border bg-bd-surface-2 px-3.5 py-[11px] no-underline hover:border-bd-accent"
        >
          <LinkIcon size={16} className="flex-none text-bd-text-3" />
          <span dir="ltr" className="min-w-0 flex-1 font-mono text-[12.5px] break-all text-bd-text">
            {telegram.link}
          </span>
          <span className="flex-none text-[11.5px] text-bd-text-3">یک‌بارمصرف</span>
        </a>
      ) : null}

      <div className="flex flex-wrap gap-[9px]">
        {linked ? (
          <button
            type="button"
            onClick={() => {
              createLink.reset();
              disconnect.mutate(undefined, {
                onSuccess: () => toast.show("اتصال تلگرام قطع شد"),
              });
            }}
            className="h-[38px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[15px] text-[13px] text-bd-danger hover:bg-bd-surface-2"
          >
            قطع اتصال
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => {
            disconnect.reset();
            createLink.mutate(undefined, {
              onSuccess: () => toast.show("لینک اتصال ساخته شد"),
            });
          }}
          disabled={createLink.isPending}
          className="h-[38px] cursor-pointer rounded-button border-0 bg-bd-accent px-[15px] text-[13px] font-medium text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
        >
          ساخت لینک اتصال
        </button>
      </div>
      {failure ? (
        <InlineAlert className="mt-3">
          {errorMessage(failure, "این کار با تلگرام انجام نشد. دوباره امتحان کن.")}
        </InlineAlert>
      ) : null}

      <ProfilePicture />
    </Section>
  );
}

/** Opens the user panel, where the owner makes and upgrades special accounts. */
function UserPanelSection() {
  const [open, setOpen] = useState(false);

  return (
    <Section>
      <h2 className="m-0 mb-1.5 text-[15px] font-semibold">کاربران</h2>
      <p className="m-0 mb-[15px] text-[13px] leading-[1.8] text-bd-text-2">
        ساختن کاربر ویژه، و تغییر نقش کاربرها بین عادی و ویژه.
      </p>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-[38px] cursor-pointer items-center gap-2 rounded-button border-0 bg-bd-accent px-[15px] text-[13px] font-medium text-bd-accent-ink hover:bg-bd-accent-hover"
      >
        <UsersThreeIcon size={16} />
        پنل یوزر
      </button>
      <UserPanelDialog open={open} onClose={() => setOpen(false)} />
    </Section>
  );
}

/** For a guest, in place of signing out: the way to keep what it has written. */
function GuestAccount() {
  const navigate = useNavigate();

  return (
    <Section>
      <h2 className="m-0 mb-1.5 text-[15px] font-semibold">هنوز حساب نساخته‌ای</h2>
      <p className="m-0 mb-[15px] text-[13px] leading-[1.8] text-bd-text-2">
        همه‌چیز بدون حساب هم کار می‌کند، اما ایده‌هایت فقط در همین مرورگر می‌ماند. با ساختن حساب،
        هرچه تا حالا نوشته‌ای در آن می‌ماند و از هر دستگاهی در دسترس است.
      </p>
      <div className="flex flex-wrap gap-[9px]">
        <button
          type="button"
          onClick={() => void navigate(ROUTES.signup)}
          className="h-[38px] cursor-pointer rounded-button border-0 bg-bd-accent px-[15px] text-[13px] font-medium text-bd-accent-ink hover:bg-bd-accent-hover"
        >
          ساخت حساب
        </button>
        <button
          type="button"
          onClick={() => void navigate(ROUTES.login)}
          className="h-[38px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[15px] text-[13px] text-bd-text hover:bg-bd-surface-2"
        >
          ورود به حساب
        </button>
      </div>
    </Section>
  );
}

function Section({ children }: { children: ReactNode }) {
  return (
    <section className="rounded-card border border-bd-border bg-bd-surface px-4 py-5 shadow-bd sm:px-[22px]">
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
      className="inline-flex h-[34px] cursor-pointer items-center gap-2 rounded-[7px] border-0 px-4 text-[13px]"
      style={{
        background: active ? "var(--color-bd-surface-3)" : "transparent",
        color: active ? "var(--color-bd-accent)" : "var(--color-bd-text-3)",
      }}
    >
      {children}
    </button>
  );
}

/**
 * Choosing, replacing or removing the profile picture shown at the top of
 * every page. The server checks the file, cuts it to a square and keeps it
 * at up to 1024 pixels a side.
 */
function ProfilePicture({ standalone = false }: { standalone?: boolean }) {
  const { user } = useApp();
  const upload = useUploadAvatar();
  const remove = useRemoveAvatar();
  const toast = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const { data: site } = useSite();
  // A file refused here, before it is sent.
  const [problem, setProblem] = useState<string | null>(null);

  const failure = upload.error ?? remove.error;
  const message =
    problem ??
    (failure ? errorMessage(failure, "ذخیرهٔ تصویر ناموفق بود. دوباره امتحان کن.") : null);

  return (
    <div className={standalone ? "" : "mt-5 border-t border-bd-border pt-5"}>
      <h3 className="m-0 mb-1.5 text-[14px] font-semibold">تصویر پروفایل</h3>
      <p className="m-0 mb-[15px] text-[13px] leading-[1.8] text-bd-text-2">
        همان تصویری که بالای صفحه کنار اعلان‌ها دیده می‌شود. عکس{" "}
        {site ? describeUpload(site.uploads.avatar) : "JPEG، PNG یا WebP"}؛ به‌شکل مربع و حداکثر
        ۱۰۲۴ پیکسل نگه داشته می‌شود.
      </p>

      <div className="flex flex-wrap items-center gap-4">
        <Avatar user={user} className="size-[72px] text-[28px]" />

        <div className="flex flex-wrap gap-[9px]">
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={upload.isPending}
            className="inline-flex h-[38px] cursor-pointer items-center gap-2 rounded-button border-0 bg-bd-accent px-[15px] text-[13px] font-medium text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
          >
            <ImageIcon size={16} />
            {upload.isPending
              ? "در حال بارگذاری…"
              : user.avatar_url
                ? "تغییر تصویر"
                : "انتخاب تصویر"}
          </button>
          {user.avatar_url ? (
            <button
              type="button"
              onClick={() => {
                setProblem(null);
                upload.reset();
                remove.mutate(undefined, {
                  onSuccess: () => toast.show("تصویر پروفایل حذف شد"),
                });
              }}
              disabled={remove.isPending}
              className="h-[38px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[15px] text-[13px] text-bd-danger hover:bg-bd-surface-2 disabled:opacity-60"
            >
              حذف تصویر
            </button>
          ) : null}
        </div>
      </div>

      {message ? <InlineAlert className="mt-3">{message}</InlineAlert> : null}

      <input
        ref={fileInput}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            remove.reset();
            upload.reset();
            const refusal = checkUpload(file, site?.uploads.avatar, "تصویر پروفایل");
            setProblem(refusal);
            if (!refusal) {
              upload.mutate(file, { onSuccess: () => toast.show("تصویر پروفایل ذخیره شد") });
            }
          }
          event.target.value = "";
        }}
      />
    </div>
  );
}
