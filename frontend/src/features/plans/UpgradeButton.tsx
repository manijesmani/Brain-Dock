import { TelegramLogoIcon } from "@phosphor-icons/react";
import type { ReactNode } from "react";

import { useSite } from "@/shared/api/queries";

/**
 * A link that opens a Telegram chat with the owner, in a new tab. It leads
 * to Telegram, so it wears Telegram's blue and white rather than the app's
 * palette.
 */
export function TelegramLink({
  handle,
  className = "",
  children,
}: {
  handle: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <a
      href={`https://t.me/${encodeURIComponent(handle)}`}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex h-[42px] w-full items-center justify-center gap-2 rounded-button bg-[#229ED9] px-4 text-[13.5px] font-semibold text-white no-underline hover:bg-[#1c8cc4] ${className}`}
    >
      <TelegramLogoIcon size={18} weight="fill" className="flex-none" />
      {children}
    </a>
  );
}

/**
 * «ارتقا به کاربر ویژه», under the sign-up form: a chat with the owner, the
 * only one who makes special accounts. Hidden if the owner's username is not
 * configured (OWNER_TELEGRAM_USERNAME).
 */
export function UpgradeButton({ className = "" }: { className?: string }) {
  const { data } = useSite();
  const handle = data?.owner_telegram;

  if (!handle) return null;

  return (
    <TelegramLink handle={handle} className={className}>
      ارتقا به کاربر ویژه
      <span dir="ltr" className="font-normal opacity-90">
        @{handle}
      </span>
    </TelegramLink>
  );
}
