import { CrownSimpleIcon } from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { UpgradeButton } from "@/features/plans/UpgradeButton";
import { useApp } from "@/features/shell/appContext";
import { toPersianDigits } from "@/shared/lib/persian";
import { Dialog } from "@/shared/ui/Dialog";
import type { CurrentUser } from "@/types/domain";

/** What was reached for: a picture or a recording, or one idea too many. */
export type PremiumReason = "media" | "ideas";

/** The mark on everything only a special account can do. */
export function Crown({ size = 11, className = "" }: { size?: number; className?: string }) {
  return <CrownSimpleIcon size={size} weight="fill" className={`text-bd-warn ${className}`} />;
}

/**
 * Why something is locked and what unlocks it. There is no payment: only the
 * owner makes a special account, so a regular one is pointed at the owner's
 * Telegram, and a guest has to sign up first so there is an account to
 * upgrade.
 */
export function PremiumNotice({
  user,
  reason,
  onClose,
}: {
  user: CurrentUser;
  reason: PremiumReason;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const guest = user.plan === "guest";
  const limit = toPersianDigits(user.idea_limit ?? 0);

  return (
    <div className="p-5">
      <div className="mb-3.5 grid size-10 place-items-center rounded-full bg-bd-warn-bg">
        <Crown size={20} />
      </div>

      <div className="mb-1.5 text-[14px] font-semibold">
        {reason === "media" ? "عکس و صدا مخصوص کاربر ویژه است" : "به سقف ایده‌ها رسیدی"}
      </div>
      <p className="m-0 text-[13px] leading-[1.8] text-bd-text-2">
        {reason === "media"
          ? "افزودن عکس، ضبط صدا و آپلود صدا فقط برای کاربر ویژه باز است."
          : `${guest ? "بدون حساب" : "با حساب عادی"} تا ${limit} ایده می‌توانی داشته باشی و ایده‌های آرشیوشده هم شمرده می‌شوند. برای ایدهٔ تازه یکی را حذف کن، یا به کاربر ویژه ارتقا بگیر.`}
      </p>
      <p className="m-0 mt-2 text-[13px] leading-[1.8] text-bd-text-2">
        {guest
          ? "برای ویژه شدن اول یک حساب بساز؛ ایده‌هایی که نوشته‌ای در آن می‌مانند."
          : "کاربر ویژه را مالک BrainDock می‌سازد؛ برای ارتقا به او پیام بده."}
      </p>

      {guest ? null : <UpgradeButton className="mt-3.5" />}

      <div className="mt-[18px] flex flex-wrap gap-[9px]">
        {guest ? (
          <button
            type="button"
            onClick={() => {
              onClose();
              void navigate(ROUTES.signup);
            }}
            className="h-[38px] cursor-pointer rounded-button border-0 bg-bd-accent px-[15px] text-[13px] font-medium text-bd-accent-ink hover:bg-bd-accent-hover"
          >
            ساخت حساب
          </button>
        ) : null}
        <button
          type="button"
          onClick={onClose}
          className="h-[38px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[15px] text-[13px] text-bd-text hover:bg-bd-surface-2"
        >
          {guest ? "بعداً" : "باشه"}
        </button>
      </div>
    </div>
  );
}

export function PremiumDialog({
  open,
  reason,
  onClose,
}: {
  open: boolean;
  reason: PremiumReason;
  onClose: () => void;
}) {
  const { user } = useApp();

  return (
    <Dialog open={open} onClose={onClose} width={400}>
      <PremiumNotice user={user} reason={reason} onClose={onClose} />
    </Dialog>
  );
}
