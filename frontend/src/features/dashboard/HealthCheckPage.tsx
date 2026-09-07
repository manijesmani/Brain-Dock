import {
  BrainIcon,
  CheckCircleIcon,
  CircleNotchIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";

import { useHealth } from "@/shared/api/health";

/**
 * Phase 0 acceptance screen. It proves the whole chain works end to end:
 * React renders right-to-left with the local Vazirmatn font and the design
 * tokens, TanStack Query calls the API through the Vite proxy, and Django
 * answers after reaching PostgreSQL.
 *
 * Phase 5 replaces this with the real dashboard.
 */
export function HealthCheckPage() {
  const query = useHealth();

  // TanStack Query's result is a discriminated union, so reading `data` only
  // inside the success branch keeps the component free of nullable access.
  const isHealthy = query.isSuccess && query.data.status === "ok";
  const health = query.isSuccess ? query.data : null;

  return (
    <main className="grid min-h-screen place-items-center p-8">
      <div className="w-90 rounded-card border border-bd-border bg-bd-surface p-7 shadow-bd">
        <div className="flex items-center gap-2.5">
          <div className="grid size-8 flex-none place-items-center rounded-[9px] bg-bd-accent text-bd-accent-ink">
            <BrainIcon size={19} />
          </div>
          <span className="text-[16.5px] font-bold tracking-tight">BrainDock</span>
        </div>

        <p className="mt-5 text-[13px] text-bd-text-2">وضعیت اتصال به سرور</p>

        <div className="mt-3 flex items-center gap-2.5 rounded-input border border-bd-border bg-bd-surface-2 px-3 py-2.5">
          {query.isPending ? (
            <>
              <CircleNotchIcon size={17} className="animate-spin text-bd-text-3" />
              <span className="text-[13px] text-bd-text-2">در حال بررسی…</span>
            </>
          ) : isHealthy ? (
            <>
              <CheckCircleIcon size={17} weight="fill" className="text-bd-accent" />
              <span className="text-[13px]">سرور و پایگاه داده سالم‌اند</span>
            </>
          ) : (
            <>
              <WarningCircleIcon size={17} weight="fill" className="text-bd-danger" />
              <span className="text-[13px] text-bd-danger">سرور در دسترس نیست</span>
            </>
          )}
        </div>

        {health ? (
          <dl className="mt-4 space-y-2 text-[12.5px] text-bd-text-3">
            <div className="flex justify-between">
              <dt>پایگاه داده</dt>
              <dd className="text-bd-text-2">{health.database === "ok" ? "سالم" : "خطا"}</dd>
            </div>
            <div className="flex justify-between">
              <dt>نسخه</dt>
              <dd className="text-bd-text-2" dir="ltr">
                {health.version}
              </dd>
            </div>
          </dl>
        ) : null}
      </div>
    </main>
  );
}
