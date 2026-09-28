import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { Crown } from "@/features/plans/PremiumNotice";
import { TelegramLink } from "@/features/plans/UpgradeButton";
import { useApp } from "@/features/shell/appContext";
import { useSite } from "@/shared/api/queries";
import { Dialog } from "@/shared/ui/Dialog";

/**
 * «خرید اشتراک»: how to become a special account. There is no payment in
 * the app -- a subscription is bought by messaging the owner on Telegram,
 * who then upgrades the account from the user panel.
 */
export function SubscribeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { user } = useApp();
  const { data } = useSite();
  const handle = data?.owner_telegram;

  return (
    <Dialog open={open} onClose={onClose} width={400}>
      <div className="p-5 sm:p-6">
        <div className="mb-3.5 grid size-11 place-items-center rounded-full bg-bd-warn-bg">
          <Crown size={22} />
        </div>

        <div className="mb-1.5 text-[15px] font-semibold">خرید اشتراک</div>
        <p className="m-0 text-[13px] leading-[1.9] text-bd-text-2">
          برای خرید اشتراک به آیدی تلگرام پیام دهید. در سریع‌ترین زمان ممکن پشتیبانی پاسخ می‌دهد.
        </p>

        {handle ? (
          <>
            <div
              dir="ltr"
              className="mt-4 rounded-[9px] border border-bd-border bg-bd-surface-2 px-3.5 py-3 text-center text-[16px] font-semibold tracking-wide select-all"
            >
              @{handle}
            </div>
            <TelegramLink handle={handle} className="mt-3">
              پیام در تلگرام
            </TelegramLink>
          </>
        ) : null}

        {/* The owner upgrades an account by its username, so a guest needs
            one first. */}
        {user.plan === "guest" ? (
          <div className="mt-4 rounded-[9px] bg-bd-warn-bg px-3.5 py-3 text-[12.5px] leading-[1.8] text-bd-warn">
            اشتراک روی حساب کاربری فعال می‌شود؛ اگر هنوز حساب ندارید، اول یکی بسازید.
            <button
              type="button"
              onClick={() => {
                onClose();
                void navigate(ROUTES.signup);
              }}
              className="ms-1.5 cursor-pointer border-0 bg-transparent p-0 text-[12.5px] font-semibold text-bd-accent underline"
            >
              ساخت حساب
            </button>
          </div>
        ) : null}

        <button
          type="button"
          onClick={onClose}
          className="mt-3 h-[38px] w-full cursor-pointer rounded-button border border-bd-border-2 bg-transparent text-[13px] text-bd-text hover:bg-bd-surface-2"
        >
          بستن
        </button>
      </div>
    </Dialog>
  );
}
