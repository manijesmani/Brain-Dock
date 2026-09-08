import {
  BellIcon,
  BellSlashIcon,
  ChecksIcon,
  TelegramLogoIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from "@/shared/api/queries";
import { formatRelativeMoment, toPersianDigits } from "@/shared/lib/persian";
import { EmptyState } from "@/shared/ui/indicators";
import type { NotificationKind } from "@/types/domain";

const ICONS: Record<NotificationKind, typeof BellIcon> = {
  reminder: BellIcon,
  stale: WarningCircleIcon,
  telegram_capture: TelegramLogoIcon,
};

export function NotificationsPage() {
  const navigate = useNavigate();
  const { data: notifications = [], isPending } = useNotifications();
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();

  const unread = notifications.filter((item) => !item.is_read).length;

  return (
    <main className="min-w-0 flex-1 px-[38px] pt-[30px] pb-[110px]">
      <header className="mb-[18px] flex max-w-[860px] items-center gap-3">
        <h1 className="m-0 text-[22px] font-bold tracking-tight">اعلان‌ها</h1>
        {unread > 0 ? (
          <span className="rounded-full bg-bd-accent px-[9px] py-0.5 text-[12px] font-semibold text-bd-accent-ink">
            {toPersianDigits(unread)} نخوانده
          </span>
        ) : null}
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => markAll.mutate()}
          disabled={unread === 0}
          className="inline-flex h-[34px] cursor-pointer items-center gap-[7px] rounded-button border border-bd-border-2 bg-transparent px-[13px] text-[13px] text-bd-text hover:bg-bd-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <ChecksIcon size={15} />
          همه را خوانده‌شده کن
        </button>
      </header>

      <div className="max-w-[860px] rounded-card border border-bd-border bg-bd-surface shadow-bd">
        {isPending ? (
          <div className="p-14 text-center text-[13.5px] text-bd-text-3">در حال بارگذاری…</div>
        ) : notifications.length === 0 ? (
          <EmptyState padded icon={<BellSlashIcon size={30} />}>
            اعلانی نداری
          </EmptyState>
        ) : (
          notifications.map((notification, index) => {
            const Icon = ICONS[notification.kind];

            return (
              <div
                key={notification.id}
                onClick={() => {
                  if (!notification.is_read) markRead.mutate(notification.id);
                  if (notification.idea !== null) {
                    void navigate(ROUTES.note.replace(":ideaId", String(notification.idea)));
                  }
                }}
                className="flex cursor-pointer items-start gap-[13px] px-[17px] py-[15px] hover:bg-bd-surface-2"
                style={{
                  borderTop: index === 0 ? "0" : "1px solid var(--color-bd-border)",
                  background: notification.is_read ? "transparent" : "var(--color-bd-accent-soft)",
                }}
              >
                <Icon size={18} className="mt-0.5 flex-none text-bd-text-2" />
                <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                  <span
                    className="text-[13.5px] leading-[1.7]"
                    style={{
                      color: notification.is_read
                        ? "var(--color-bd-text-2)"
                        : "var(--color-bd-text)",
                    }}
                  >
                    {notification.text}
                  </span>
                  <span className="text-[12px] text-bd-text-3">
                    {formatRelativeMoment(notification.created_at)}
                  </span>
                </div>
                {!notification.is_read ? (
                  <span className="mt-1.5 size-[7px] flex-none rounded-full bg-bd-accent" />
                ) : null}
              </div>
            );
          })
        )}
      </div>
    </main>
  );
}
