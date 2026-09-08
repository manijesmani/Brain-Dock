import type { IdeaPriority, IdeaStatus } from "@/types/domain";

/**
 * The Persian vocabulary and the colour tokens for an idea's status and
 * priority, in one place so a label is never spelled twice.
 */

/** Status token suffixes, as the design names them. */
const STATUS_TOKEN: Record<IdeaStatus, string> = {
  idea: "idea",
  planned: "plan",
  doing: "doing",
  done: "done",
  archived: "arch",
};

export const STATUS_LABELS: Record<IdeaStatus, string> = {
  idea: "ایده",
  planned: "برنامه‌ریزی‌شده",
  doing: "در حال انجام",
  done: "انجام‌شده",
  archived: "آرشیو",
};

export const PRIORITY_LABELS: Record<IdeaPriority, string> = {
  low: "کم",
  mid: "متوسط",
  high: "زیاد",
};

export function statusColor(status: IdeaStatus): string {
  return `var(--color-st-${STATUS_TOKEN[status]})`;
}

export function statusBackground(status: IdeaStatus): string {
  return `var(--color-st-${STATUS_TOKEN[status]}-bg)`;
}
