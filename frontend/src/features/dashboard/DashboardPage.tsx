import {
  BellIcon,
  BellSlashIcon,
  CalendarBlankIcon,
  CheckCircleIcon,
  PlayCircleIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { useApp } from "@/features/shell/appContext";
import { useIdeas, useReminders } from "@/shared/api/queries";
import {
  daysSince,
  formatJalaliDateWithWeekday,
  formatTimeOfDay,
  toPersianDigits,
} from "@/shared/lib/persian";
import {
  CategoryDot,
  EmptyState,
  PriorityDots,
  ProgressBar,
  StatusPill,
} from "@/shared/ui/indicators";
import type { IdeaStatus, IdeaSummary, Reminder } from "@/types/domain";

export function DashboardPage() {
  const navigate = useNavigate();
  const { user, categories } = useApp();

  const { data: today = [] } = useReminders({ window: "today" });
  const { data: week = [] } = useReminders({ window: "week" });
  const { data: stale } = useIdeas({ stale: true, page_size: 50 });
  const { data: doing } = useIdeas({ status: "doing", page_size: 50 });

  const openIdea = (id: number) => void navigate(ROUTES.note.replace(":ideaId", String(id)));
  const categoryOf = (id: number | null) => categories.find((item) => item.id === id) ?? null;

  const staleRows = stale?.results ?? [];
  const doingRows = doing?.results ?? [];

  // Each section's bar is "how many of these are finished", which is what
  // prog() computes in the design file.
  const doneAmong = <T,>(rows: T[], status: (row: T) => IdeaStatus) =>
    rows.filter((row) => status(row) === "done").length;

  return (
    <main className="min-w-0 flex-1 px-[38px] pt-[30px] pb-[110px]">
      <header className="mb-[26px]">
        <h1 className="m-0 mb-1 text-[26px] font-bold tracking-tight">سلام {user.display_name}</h1>
        <div className="text-[13.5px] text-bd-text-2">
          {formatJalaliDateWithWeekday(new Date())}
        </div>
      </header>

      <Section
        title="یادآوری‌های امروز"
        count={today.length}
        done={doneAmong(today, (row) => row.idea_status)}
        total={today.length}
        empty={
          <EmptyState icon={<BellSlashIcon size={22} />}>برای امروز یادآوری‌ای ثبت نشده</EmptyState>
        }
      >
        {today.map((reminder, index) => (
          <ReminderRow
            key={reminder.id}
            reminder={reminder}
            first={index === 0}
            accent
            onOpen={() => openIdea(reminder.idea)}
          />
        ))}
      </Section>

      <Section
        title="این هفته"
        count={week.length}
        done={doneAmong(week, (row) => row.idea_status)}
        total={week.length}
        empty={
          <EmptyState icon={<CalendarBlankIcon size={22} />}>
            این هفته یادآوری‌ای در پیش نیست
          </EmptyState>
        }
      >
        {week.map((reminder, index) => (
          <ReminderRow
            key={reminder.id}
            reminder={reminder}
            first={index === 0}
            onOpen={() => openIdea(reminder.idea)}
          />
        ))}
      </Section>

      <Section
        title="ایده‌های راکد"
        count={staleRows.length}
        done={doneAmong(staleRows, (row) => row.status)}
        total={staleRows.length}
        empty={<EmptyState icon={<CheckCircleIcon size={22} />}>ایدهٔ راکدی نداری</EmptyState>}
      >
        {staleRows.map((idea, index) => (
          <div
            key={idea.id}
            onClick={() => openIdea(idea.id)}
            className="flex cursor-pointer items-center gap-3 px-[15px] py-3 hover:bg-bd-surface-2"
            style={{ borderTop: index === 0 ? "0" : "1px solid var(--color-bd-border)" }}
          >
            <CategoryDot color={categoryOf(idea.category)?.color ?? null} />
            <span className="min-w-0 flex-1 overflow-hidden text-[13.5px] font-medium text-ellipsis whitespace-nowrap">
              {idea.title}
            </span>
            <span className="text-[12px] text-bd-text-3">
              {categoryOf(idea.category)?.name ?? "بدون دسته"}
            </span>
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-[9px] py-[3px] text-[12px] font-medium"
              style={{
                background: "var(--color-bd-warn-bg)",
                color: "var(--color-bd-warn)",
              }}
            >
              <WarningCircleIcon size={13} />
              {toPersianDigits(daysSince(idea.updated_at))} روز بدون تغییر
            </span>
          </div>
        ))}
      </Section>

      <Section
        title="در حال انجام"
        count={doingRows.length}
        done={doneAmong(doingRows, (row) => row.status)}
        total={doingRows.length}
        last
        empty={
          <EmptyState icon={<PlayCircleIcon size={22} />}>ایده‌ای در حال انجام نیست</EmptyState>
        }
      >
        {doingRows.map((idea, index) => (
          <DoingRow
            key={idea.id}
            idea={idea}
            first={index === 0}
            color={categoryOf(idea.category)?.color ?? null}
            onOpen={() => openIdea(idea.id)}
          />
        ))}
      </Section>
    </main>
  );
}

function Section({
  title,
  count,
  done,
  total,
  children,
  empty,
  last = false,
}: {
  title: string;
  count: number;
  done: number;
  total: number;
  children: ReactNode;
  empty: ReactNode;
  last?: boolean;
}) {
  return (
    <section className={`max-w-[1000px] ${last ? "" : "mb-6"}`}>
      <div className="mb-2.5 flex items-center gap-2">
        <h2 className="m-0 text-[14px] font-semibold">{title}</h2>
        <span className="text-[11.5px] text-bd-text-3">{toPersianDigits(count)}</span>
        <div className="flex-1" />
        <ProgressBar done={done} total={total} />
      </div>
      <div className="rounded-card border border-bd-border bg-bd-surface shadow-bd">
        {count === 0 ? empty : children}
      </div>
    </section>
  );
}

function ReminderRow({
  reminder,
  first,
  accent = false,
  onOpen,
}: {
  reminder: Reminder;
  first: boolean;
  accent?: boolean;
  onOpen: () => void;
}) {
  return (
    <div
      onClick={onOpen}
      className="flex cursor-pointer items-center gap-3 px-[15px] py-3 hover:bg-bd-surface-2"
      style={{ borderTop: first ? "0" : "1px solid var(--color-bd-border)" }}
    >
      <CategoryDot color={reminder.idea_category_color} />
      <span className="min-w-0 flex-1 overflow-hidden text-[13.5px] font-medium text-ellipsis whitespace-nowrap">
        {reminder.idea_title}
      </span>
      <span className="text-[12px] text-bd-text-3">
        {reminder.idea_category_name ?? "بدون دسته"}
      </span>
      <span
        className="inline-flex items-center gap-[5px] text-[12.5px]"
        style={{
          color: accent ? "var(--color-bd-accent)" : "var(--color-bd-text-2)",
          fontWeight: accent ? 500 : 400,
        }}
      >
        <BellIcon size={14} />
        {accent
          ? reminder.next_run_at
            ? formatTimeOfDay(reminder.next_run_at)
            : ""
          : reminder.description}
      </span>
    </div>
  );
}

function DoingRow({
  idea,
  first,
  color,
  onOpen,
}: {
  idea: IdeaSummary;
  first: boolean;
  color: string | null;
  onOpen: () => void;
}) {
  return (
    <div
      onClick={onOpen}
      className="flex cursor-pointer items-center gap-3 px-[15px] py-3 hover:bg-bd-surface-2"
      style={{ borderTop: first ? "0" : "1px solid var(--color-bd-border)" }}
    >
      <CategoryDot color={color} />
      <span className="min-w-0 flex-1 overflow-hidden text-[13.5px] font-medium text-ellipsis whitespace-nowrap">
        {idea.title}
      </span>
      <PriorityDots priority={idea.priority} />
      <StatusPill status={idea.status} />
    </div>
  );
}
