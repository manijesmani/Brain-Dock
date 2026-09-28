import {
  DesktopIcon,
  DeviceMobileIcon,
  DeviceTabletIcon,
  QuestionIcon,
  SignOutIcon,
} from "@phosphor-icons/react";
import { useState } from "react";

import { errorMessage } from "@/shared/api/errors";
import { useDevices, useSignOutDevice, useSignOutOtherDevices } from "@/shared/api/queries";
import { useToast } from "@/shared/hooks/useToast";
import { formatRelativeMoment, toPersianDigits } from "@/shared/lib/persian";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import type { Device } from "@/types/domain";

const ICONS = {
  mobile: DeviceMobileIcon,
  tablet: DeviceTabletIcon,
  desktop: DesktopIcon,
  unknown: QuestionIcon,
} as const;

/**
 * «دستگاه‌های فعال»: every browser signed in to the account, with its address
 * and when it was last used, and a way to sign any of them out. Not rendered
 * for a guest, which has only the one browser; the API refuses it anyway.
 */
export function DevicesSection() {
  const { data: devices = [], isPending, isError, error } = useDevices();
  const signOut = useSignOutDevice();
  const signOutOthers = useSignOutOtherDevices();
  const toast = useToast();

  const [target, setTarget] = useState<Device | null>(null);
  const [allOthers, setAllOthers] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const others = devices.filter((device) => !device.current).length;

  const confirmOne = () => {
    if (!target) return;
    setFailure(null);
    signOut.mutate(target.id, {
      onSuccess: () => {
        setTarget(null);
        toast.show("دستگاه از حساب خارج شد");
      },
      onError: (caught) =>
        setFailure(errorMessage(caught, "خارج کردن دستگاه ناموفق بود. دوباره امتحان کن.")),
    });
  };

  const confirmAll = () => {
    setFailure(null);
    signOutOthers.mutate(undefined, {
      onSuccess: ({ signed_out: count }) => {
        setAllOthers(false);
        toast.show(`${toPersianDigits(count)} دستگاه از حساب خارج شد`);
      },
      onError: (caught) =>
        setFailure(errorMessage(caught, "خارج کردن دستگاه‌ها ناموفق بود. دوباره امتحان کن.")),
    });
  };

  return (
    <>
      <div className="mb-1.5 flex items-center gap-2">
        <h2 className="m-0 text-[15px] font-semibold">دستگاه‌های فعال</h2>
        {devices.length > 0 ? (
          <span className="text-[12px] text-bd-text-3">{toPersianDigits(devices.length)}</span>
        ) : null}
      </div>
      <p className="m-0 mb-[15px] text-[13px] leading-[1.8] text-bd-text-2">
        جاهایی که با این حساب وارد شده‌ای. اگر دستگاهی را نمی‌شناسی، از حساب خارجش کن و رمزت را عوض
        کن.
      </p>

      <div className="overflow-hidden rounded-[9px] border border-bd-border">
        {isPending ? (
          <div className="px-3.5 py-6 text-center text-[13px] text-bd-text-3">در حال بارگذاری…</div>
        ) : isError ? (
          <div className="p-3">
            <InlineAlert>
              {errorMessage(error, "فهرست دستگاه‌ها بارگذاری نشد. صفحه را دوباره باز کن.")}
            </InlineAlert>
          </div>
        ) : (
          devices.map((device, index) => (
            <DeviceRow
              key={device.id}
              device={device}
              first={index === 0}
              onSignOut={() => {
                setFailure(null);
                setTarget(device);
              }}
            />
          ))
        )}
      </div>

      {others > 0 ? (
        <button
          type="button"
          onClick={() => {
            setFailure(null);
            setAllOthers(true);
          }}
          className="mt-3.5 inline-flex h-[38px] cursor-pointer items-center gap-[7px] rounded-button border border-bd-border-2 bg-transparent px-[15px] text-[13px] text-bd-danger hover:bg-bd-surface-2 pointer-coarse:h-11"
        >
          <SignOutIcon size={16} />
          خروج از همهٔ دستگاه‌های دیگر
        </button>
      ) : null}

      <ConfirmDialog
        open={target !== null}
        title="این دستگاه از حساب خارج شود؟"
        confirmLabel="خروج"
        danger
        pending={signOut.isPending}
        error={failure}
        onConfirm={confirmOne}
        onClose={() => {
          setTarget(null);
          setFailure(null);
        }}
      >
        <span className="font-semibold text-bd-text">{target?.name}</span>
        {target?.ip_address ? (
          <span dir="ltr" className="ms-1.5 text-bd-text-3">
            {target.ip_address}
          </span>
        ) : null}
        <span className="mt-1 block">برای استفادهٔ دوباره باید با رمز وارد شود.</span>
      </ConfirmDialog>

      <ConfirmDialog
        open={allOthers}
        title="از همهٔ دستگاه‌های دیگر خارج شوی؟"
        confirmLabel="خروج از همه"
        danger
        pending={signOutOthers.isPending}
        error={failure}
        onConfirm={confirmAll}
        onClose={() => {
          setAllOthers(false);
          setFailure(null);
        }}
      >
        فقط همین دستگاه وارد می‌ماند؛ {toPersianDigits(others)} دستگاه دیگر برای استفادهٔ دوباره
        باید با رمز وارد شوند.
      </ConfirmDialog>
    </>
  );
}

function DeviceRow({
  device,
  first,
  onSignOut,
}: {
  device: Device;
  first: boolean;
  onSignOut: () => void;
}) {
  const Icon = ICONS[device.kind];

  const lastUse = device.current
    ? "در حال استفاده"
    : device.last_seen_at
      ? `آخرین استفاده: ${formatRelativeMoment(device.last_seen_at)}`
      : "آخرین استفاده: نامشخص";

  return (
    <div
      className="flex items-center gap-3 px-3.5 py-[11px]"
      style={{ borderTop: first ? "0" : "1px solid var(--color-bd-border)" }}
    >
      <span className="grid size-9 flex-none place-items-center rounded-full bg-bd-surface-2 text-bd-text-2">
        <Icon size={18} />
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <span title={device.user_agent || undefined} className="text-[13.5px] font-medium">
            {device.name}
          </span>
          {device.current ? (
            <span className="rounded-full bg-bd-accent-soft px-2 py-px text-[11px] font-semibold text-bd-accent">
              همین دستگاه
            </span>
          ) : null}
        </span>
        <span className="mt-0.5 block text-[12px] leading-[1.8] text-bd-text-3">
          <span>آی‌پی: </span>
          <span dir="ltr">{device.ip_address ?? "نامشخص"}</span>
          <span className="opacity-50"> · </span>
          <span>{lastUse}</span>
          {device.signed_in_at ? (
            <>
              <span className="opacity-50"> · </span>
              <span>ورود: {formatRelativeMoment(device.signed_in_at)}</span>
            </>
          ) : null}
        </span>
      </span>

      {device.current ? null : (
        <button
          type="button"
          onClick={onSignOut}
          aria-label={`خروج ${device.name} از حساب`}
          className="h-8 flex-none cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-3 text-[12.5px] text-bd-danger hover:bg-bd-surface-2 pointer-coarse:h-9"
        >
          خروج
        </button>
      )}
    </div>
  );
}
