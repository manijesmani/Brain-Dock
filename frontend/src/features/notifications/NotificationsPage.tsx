import {
  BellIcon,
  BellSlashIcon,
  ChecksIcon,
  TelegramLogoIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { PageHeader } from "@/features/shell/PageHeader";
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
    <main className="min-w-0 flex-1 px-[47.5px] pt-[32.5px] pb-[137.5px]">
      <PageHeader
        title="اعلان‌ها"
        subtitle={unread > 0 ? `${toPersianDigits(unread)} نخوانده` : "همه خوانده شده"}
      />

      <div className="mb-[17.5px] flex max-w-[1075px] items-center justify-end">
        <button
          type="button"
          onClick={() => markAll.mutate()}
          disabled={unread === 0}
          className="inline-flex h-[42.5px] cursor-pointer items-center gap-[9px] rounded-button border border-bd-border-2 bg-transparent px-[16px] text-[16px] text-bd-text hover:bg-bd-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <ChecksIcon size={19} />
          همه را خوانده‌شده کن
        </button>
      </div>

      <div className="max-w-[1075px] rounded-card border border-bd-border bg-bd-surface shadow-bd">
        {isPending ? (
          <div className="p-14 text-center text-[17px] text-bd-text-3">در حال بارگذاری…</div>
        ) : notifications.length === 0 ? (
          <EmptyState padded icon={<BellSlashIcon size={37.5} />}>
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
                className="flex cursor-pointer items-start gap-[16px] px-[21px] py-[19px] hover:bg-bd-surface-2"
                style={{
                  borderTop: index === 0 ? "0" : "1px solid var(--color-bd-border)",
                  background: notification.is_read ? "transparent" : "var(--color-bd-accent-soft)",
                }}
              >
                <Icon size={22.5} className="mt-0.5 flex-none text-bd-text-2" />
                <div className="flex min-w-0 flex-1 flex-col gap-[4px]">
                  <span
                    className="text-[17px] leading-[1.7]"
                    style={{
                      color: notification.is_read
                        ? "var(--color-bd-text-2)"
                        : "var(--color-bd-text)",
                    }}
                  >
                    {notification.text}
                  </span>
                  <span className="text-[15px] text-bd-text-3">
                    {formatRelativeMoment(notification.created_at)}
                  </span>
                </div>
                {!notification.is_read ? (
                  <span className="mt-1.5 size-[9px] flex-none rounded-full bg-bd-accent" />
                ) : null}
              </div>
            );
          })
        )}
      </div>
    </main>
  );
}
