import type { ReactNode } from "react";

import { toPersianDigits } from "@/shared/lib/persian";
import { STATUS_LABELS, statusBackground, statusColor } from "@/shared/ui/status";
import type { IdeaPriority, IdeaStatus } from "@/types/domain";

export function StatusPill({ status }: { status: IdeaStatus }) {
  return (
    <span
      className="flex-none rounded-full px-[10px] py-[3px] text-[12px] font-medium"
      style={{ background: statusBackground(status), color: statusColor(status) }}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

/**
 * Status as a coloured dot and label, the form the idea table uses. Inside a
 * lifted table row both follow the row's ink instead of the status colour.
 */
export function StatusDot({ status }: { status: IdeaStatus }) {
  return (
    <span
      className="flex min-w-0 items-center gap-[7px] text-[12.5px] font-medium"
      style={{ color: `var(--row-ink, ${statusColor(status)})` }}
    >
      <span className="size-[7px] flex-none rounded-full bg-current" />
      <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">
        {STATUS_LABELS[status]}
      </span>
    </span>
  );
}

/**
 * Priority as three dots: one lit for low, two for medium, three for high.
 * The unlit ones stay faintly visible rather than disappearing, so the
 * control keeps a constant width.
 */
export function PriorityDots({ priority }: { priority: IdeaPriority }) {
  const lit = { low: 1, mid: 2, high: 3 }[priority];

  return (
    <span title="اولویت" className="inline-flex flex-none items-center gap-[3px]">
      {[1, 2, 3].map((step) => (
        <span
          key={step}
          // A table row supplies --row-fg-2; everywhere else the fallback applies.
          className="block size-[5px] rounded-full bg-[var(--row-fg-2,var(--color-bd-text-2))]"
          style={{ opacity: step <= lit ? 1 : 0.22 }}
        />
      ))}
    </span>
  );
}

export function CategoryDot({ color, size = 7 }: { color: string | null; size?: number }) {
  return (
    <span
      className="block flex-none rounded-full"
      style={{ width: size, height: size, background: color ?? "var(--color-bd-text-3)" }}
    />
  );
}

export function StaleBadge() {
  return (
    <span
      className="flex-none rounded-full px-[7px] py-px text-[11px] font-medium"
      style={{
        background: "var(--color-bd-warn-bg)",
        color: "var(--row-ink, var(--color-bd-warn))",
      }}
    >
      راکد
    </span>
  );
}

/** The thin bar that shows how much of a dashboard section is done. */
export function ProgressBar({ done, total }: { done: number; total: number }) {
  const percent = total === 0 ? 0 : Math.round((done / total) * 100);

  return (
    <>
      <span className="text-[11px] text-bd-text-3">
        {toPersianDigits(done)} از {toPersianDigits(total)}
      </span>
      <span className="block h-1 w-[74px] overflow-hidden rounded-full bg-bd-surface-3">
        <span
          className="block h-1 rounded-full bg-bd-accent transition-[width] duration-300"
          style={{ width: `${percent}%` }}
        />
      </span>
    </>
  );
}

export function EmptyState({
  icon,
  children,
  padded = false,
}: {
  icon: ReactNode;
  children: ReactNode;
  padded?: boolean;
}) {
  return (
    <div
      className="flex flex-col items-center gap-2 px-4 text-bd-text-3"
      style={{ paddingBlock: padded ? 70 : 30 }}
    >
      <span style={{ opacity: 0.65 }}>{icon}</span>
      <div className="text-[13.5px]">{children}</div>
    </div>
  );
}
