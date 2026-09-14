import {
  ArrowRightIcon,
  BellSlashIcon,
  CalendarDotsIcon,
  CalendarIcon,
  CaretDownIcon,
  CaretLeftIcon,
  CaretRightIcon,
  CheckCircleIcon,
  ClockIcon,
  SunHorizonIcon,
} from "@phosphor-icons/react";
import { useMemo, useState } from "react";

import { useDeleteReminder, useReminders, useSaveReminder } from "@/shared/api/queries";
import {
  JALALI_MONTHS,
  JALALI_WEEKDAYS,
  daysInJalaliMonth,
  formatClock,
  formatJalaliDate,
  formatJalaliDateWithWeekday,
  jalaliToGregorian,
  jalaliWeekday,
  toJalali,
  toPersianDigits,
} from "@/shared/lib/persian";
import { Dialog } from "@/shared/ui/Dialog";
import { Switch } from "@/shared/ui/Switch";
import type { RecurrenceKind, Reminder } from "@/types/domain";

/** The dialog's own fifth option: no reminder at all. */
type DraftKind = RecurrenceKind | "none";

const TYPES: { kind: DraftKind; label: string; Icon: typeof BellSlashIcon }[] = [
  { kind: "none", label: "بدون یادآوری", Icon: BellSlashIcon },
  { kind: "daily", label: "روزانه", Icon: SunHorizonIcon },
  { kind: "weekly", label: "هفتگی", Icon: CalendarDotsIcon },
  { kind: "monthly", label: "ماهانه", Icon: CalendarIcon },
  { kind: "exact", label: "تاریخ و ساعت دقیق", Icon: ClockIcon },
];

const TYPE_LABELS: Record<DraftKind, string> = {
  none: "بدون یادآوری",
  daily: "روزانه",
  weekly: "هفتگی",
  monthly: "ماهانه",
  exact: "تاریخ و ساعت دقیق",
};

/** The dialog offers these minutes only, and the API accepts no others. */
const MINUTES = [0, 15, 30, 45];

interface Draft {
  kind: DraftKind;
  hour: number;
  minute: number;
  weekdays: number[];
  dayOfMonth: number;
  date: [number, number, number];
  active: boolean;
}

function draftFrom(reminder: Reminder | undefined): Draft {
  const today = toJalali(new Date());

  if (!reminder) {
    return {
      kind: "none",
      hour: 9,
      minute: 0,
      weekdays: [],
      dayOfMonth: today.day,
      date: [today.year, today.month, today.day],
      active: true,
    };
  }

  return {
    kind: reminder.recurrence,
    hour: reminder.hour,
    minute: reminder.minute,
    weekdays: reminder.weekdays,
    dayOfMonth: reminder.day_of_month ?? today.day,
    date: reminder.exact_date ?? [today.year, today.month, today.day],
    active: reminder.is_active,
  };
}

interface ReminderDialogProps {
  open: boolean;
  ideaId: number | null;
  onClose: () => void;
}

export function ReminderDialog({ open, ideaId, onClose }: ReminderDialogProps) {
  const { data: reminders } = useReminders();
  const existing = reminders?.find((item) => item.idea === ideaId);

  if (!open || ideaId === null) return null;

  return (
    // Keyed by the idea and the reminder it already has, so the draft starts
    // from the saved rule instead of being copied into state by an effect.
    <ReminderForm
      key={`${ideaId}:${existing?.id ?? "new"}`}
      ideaId={ideaId}
      existing={existing}
      onClose={onClose}
    />
  );
}

function ReminderForm({
  ideaId,
  existing,
  onClose,
}: {
  ideaId: number;
  existing: Reminder | undefined;
  onClose: () => void;
}) {
  const initial = draftFrom(existing);

  const [draft, setDraft] = useState<Draft>(initial);
  const [step, setStep] = useState(initial.kind === "none" ? 1 : 2);
  const [menu, setMenu] = useState<"hour" | "minute" | null>(null);
  const [calendar, setCalendar] = useState<[number, number]>([initial.date[0], initial.date[1]]);

  const save = useSaveReminder();
  const remove = useDeleteReminder();

  const patch = (changes: Partial<Draft>) => setDraft((current) => ({ ...current, ...changes }));

  const preview = useMemo(() => nextOccurrence(draft), [draft]);

  const calendarCells = useMemo(() => {
    const [year, month] = calendar;
    const length = daysInJalaliMonth(year, month);
    const firstWeekday = jalaliWeekday(jalaliToGregorian({ year, month, day: 1 }));

    const blanks = Array.from({ length: firstWeekday }, () => null);
    const days = Array.from({ length }, (_, index) => index + 1);
    return [...blanks, ...days];
  }, [calendar]);

  const today = toJalali(new Date());

  const commit = async () => {
    if (draft.kind === "none") {
      if (existing) await remove.mutateAsync({ id: existing.id, idea: ideaId });
      onClose();
      return;
    }

    await save.mutateAsync({
      id: existing?.id,
      idea: ideaId,
      recurrence: draft.kind,
      hour: draft.hour,
      minute: draft.minute,
      weekdays: draft.kind === "weekly" ? draft.weekdays : [],
      day_of_month: draft.kind === "monthly" ? draft.dayOfMonth : null,
      exact_date: draft.kind === "exact" ? draft.date : null,
      is_active: draft.active,
    });
    onClose();
  };

  const canSave = draft.kind !== "weekly" || draft.weekdays.length > 0;

  return (
    <Dialog open onClose={onClose} width={590} scrollable>
      <div className="flex items-center gap-2.5 border-b border-bd-border px-5 pt-[21px] pb-[17.5px]">
        {step === 2 ? (
          <button
            type="button"
            onClick={() => setStep(1)}
            title="مرحلهٔ قبل"
            className="grid size-7 cursor-pointer place-items-center rounded-[9px] border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2"
          >
            <ArrowRightIcon size={19} />
          </button>
        ) : null}
        <span className="flex-1 text-[17.5px] font-semibold">یادآوری</span>
        <span className="text-[15.5px] text-bd-text-3">{TYPE_LABELS[draft.kind]}</span>
      </div>

      <div className="px-5 py-[22.5px]">
        {step === 1 ? (
          <div className="flex flex-col gap-2">
            {TYPES.map(({ kind, label, Icon }) => {
              const selected = draft.kind === kind;
              return (
                <button
                  key={kind}
                  type="button"
                  onClick={() => {
                    patch({ kind });
                    setStep(kind === "none" ? 1 : 2);
                  }}
                  className="flex h-11 cursor-pointer items-center gap-[14px] rounded-[11px] px-[17.5px] text-right text-[17px] text-bd-text"
                  style={{
                    border: `1px solid ${selected ? "var(--color-bd-accent)" : "var(--color-bd-border)"}`,
                    background: selected ? "var(--color-bd-accent-soft)" : "transparent",
                  }}
                >
                  <Icon size={21} className="text-bd-text-2" />
                  <span className="flex-1 text-right">{label}</span>
                  {selected ? (
                    <CheckCircleIcon size={21} weight="fill" className="text-bd-accent" />
                  ) : null}
                </button>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-col gap-[22.5px]">
            {draft.kind === "weekly" ? (
              <div>
                <div className="mb-[11px] text-[15.5px] text-bd-text-2">روزهای هفته</div>
                <div className="flex flex-wrap gap-1.5">
                  {JALALI_WEEKDAYS.map((label, index) => {
                    const selected = draft.weekdays.includes(index);
                    return (
                      <button
                        key={label}
                        type="button"
                        onClick={() =>
                          patch({
                            weekdays: selected
                              ? draft.weekdays.filter((day) => day !== index)
                              : [...draft.weekdays, index],
                          })
                        }
                        className="h-[42.5px] cursor-pointer rounded-button px-3 text-[15.5px]"
                        style={{
                          border: `1px solid ${selected ? "var(--color-bd-accent)" : "var(--color-bd-border)"}`,
                          background: selected ? "var(--color-bd-accent-soft)" : "transparent",
                          color: selected ? "var(--color-bd-text)" : "var(--color-bd-text-2)",
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {draft.kind === "monthly" ? (
              <div>
                <div className="mb-[11px] text-[15.5px] text-bd-text-2">روز ماه</div>
                <div className="grid grid-cols-7 gap-[6px]">
                  {Array.from({ length: 31 }, (_, index) => index + 1).map((day) => {
                    const selected = draft.dayOfMonth === day;
                    return (
                      <button
                        key={day}
                        type="button"
                        onClick={() => patch({ dayOfMonth: day })}
                        className="h-8 cursor-pointer rounded-[9px] border border-bd-border text-[15.5px]"
                        style={{
                          background: selected ? "var(--color-bd-accent)" : "transparent",
                          color: selected ? "var(--color-bd-accent-ink)" : "var(--color-bd-text-2)",
                        }}
                      >
                        {toPersianDigits(day)}
                      </button>
                    );
                  })}
                </div>
                <p className="mt-2.5 text-[14.5px] leading-relaxed text-bd-text-3">
                  اگر ماهی این روز را نداشته باشد، یادآوری روی آخرین روز همان ماه اجرا می‌شود.
                </p>
              </div>
            ) : null}

            {draft.kind === "exact" ? (
              <div>
                <div className="mb-2.5 flex items-center gap-2">
                  <button
                    type="button"
                    title="ماه بعد"
                    onClick={() =>
                      setCalendar(([year, month]) =>
                        month === 12 ? [year + 1, 1] : [year, month + 1],
                      )
                    }
                    className="grid size-7 cursor-pointer place-items-center rounded-[9px] border border-bd-border bg-transparent text-bd-text-2"
                  >
                    <CaretLeftIcon size={17.5} />
                  </button>
                  <span className="flex-1 text-center text-[17px] font-semibold">
                    {JALALI_MONTHS[calendar[1] - 1]} {toPersianDigits(calendar[0])}
                  </span>
                  <button
                    type="button"
                    title="ماه قبل"
                    onClick={() =>
                      setCalendar(([year, month]) =>
                        month === 1 ? [year - 1, 12] : [year, month - 1],
                      )
                    }
                    className="grid size-7 cursor-pointer place-items-center rounded-[9px] border border-bd-border bg-transparent text-bd-text-2"
                  >
                    <CaretRightIcon size={17.5} />
                  </button>
                </div>

                <div className="mb-1.5 grid grid-cols-7 gap-1 text-center text-[14px] text-bd-text-3">
                  {["ش", "ی", "د", "س", "چ", "پ", "ج"].map((letter) => (
                    <span key={letter}>{letter}</span>
                  ))}
                </div>

                <div className="grid grid-cols-7 gap-1">
                  {calendarCells.map((day, index) => {
                    if (day === null) return <span key={`blank-${index}`} className="h-8" />;

                    const selected =
                      draft.date[0] === calendar[0] &&
                      draft.date[1] === calendar[1] &&
                      draft.date[2] === day;
                    const isToday =
                      today.year === calendar[0] &&
                      today.month === calendar[1] &&
                      today.day === day;

                    return (
                      <button
                        key={day}
                        type="button"
                        onClick={() => patch({ date: [calendar[0], calendar[1], day] })}
                        className="h-8 cursor-pointer rounded-button border-0 text-[15.5px]"
                        style={{
                          background: selected
                            ? "var(--color-bd-accent)"
                            : isToday
                              ? "var(--color-bd-surface-3)"
                              : "transparent",
                          color: selected ? "var(--color-bd-accent-ink)" : "var(--color-bd-text)",
                        }}
                      >
                        {toPersianDigits(day)}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            <div>
              <div className="mb-[11px] text-[15.5px] text-bd-text-2">ساعت</div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      setMenu(menu === "hour" ? null : "hour");
                    }}
                    className="inline-flex h-[47.5px] cursor-pointer items-center gap-2 rounded-button border border-bd-border-2 bg-bd-bg px-[17.5px] text-[17.5px] text-bd-text"
                  >
                    <ClockIcon size={19} className="text-bd-text-3" />
                    {formatClock(draft.hour, draft.minute)}
                    <CaretDownIcon size={15} className="text-bd-text-3" />
                  </button>
                  {menu === "hour" ? (
                    <>
                      <div className="fixed inset-0 z-[1450]" onClick={() => setMenu(null)} />
                      <div
                        className="absolute top-11 z-[1500] grid w-[287.5px] grid-cols-6 gap-1 rounded-card border border-bd-border-2 bg-bd-surface-2 p-2 shadow-bd-lg"
                        style={{ insetInlineStart: 0, animation: "bd-pop 150ms ease-out" }}
                      >
                        {Array.from({ length: 24 }, (_, hour) => (
                          <button
                            key={hour}
                            type="button"
                            onClick={() => {
                              patch({ hour });
                              setMenu(null);
                            }}
                            className="h-7 cursor-pointer rounded-[7.5px] border-0 text-[15px]"
                            style={{
                              background:
                                hour === draft.hour
                                  ? "var(--color-bd-accent)"
                                  : "var(--color-bd-surface-3)",
                              color:
                                hour === draft.hour
                                  ? "var(--color-bd-accent-ink)"
                                  : "var(--color-bd-text)",
                            }}
                          >
                            {toPersianDigits(hour)}
                          </button>
                        ))}
                      </div>
                    </>
                  ) : null}
                </div>

                <div className="relative">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      setMenu(menu === "minute" ? null : "minute");
                    }}
                    className="h-[47.5px] cursor-pointer rounded-button border border-bd-border-2 bg-bd-bg px-[17.5px] text-[16px] text-bd-text-2"
                  >
                    دقیقه
                  </button>
                  {menu === "minute" ? (
                    <>
                      <div className="fixed inset-0 z-[1450]" onClick={() => setMenu(null)} />
                      <div
                        className="absolute top-11 z-[1500] flex gap-1 rounded-card border border-bd-border-2 bg-bd-surface-2 p-2 shadow-bd-lg"
                        style={{ insetInlineStart: 0, animation: "bd-pop 150ms ease-out" }}
                      >
                        {MINUTES.map((minute) => (
                          <button
                            key={minute}
                            type="button"
                            onClick={() => {
                              patch({ minute });
                              setMenu(null);
                            }}
                            className="h-7 w-[47.5px] cursor-pointer rounded-[7.5px] border-0 text-[15px]"
                            style={{
                              background:
                                minute === draft.minute
                                  ? "var(--color-bd-accent)"
                                  : "var(--color-bd-surface-3)",
                              color:
                                minute === draft.minute
                                  ? "var(--color-bd-accent-ink)"
                                  : "var(--color-bd-text)",
                            }}
                          >
                            {toPersianDigits(String(minute).padStart(2, "0"))}
                          </button>
                        ))}
                      </div>
                    </>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-[16px] border-t border-bd-border px-5 py-[19px]">
        <div className="flex items-center gap-3">
          <Switch
            checked={draft.active}
            onChange={(active) => patch({ active })}
            label="فعال بودن یادآوری"
          />
          <span className="flex-1 text-[15.5px] text-bd-text-2">
            {preview && draft.active
              ? `یادآوری بعدی: ${preview}، ساعت ${formatClock(draft.hour, draft.minute)}`
              : "یادآوری‌ای تنظیم نشده"}
          </span>
        </div>
        <div className="flex gap-[11px]">
          <button
            type="button"
            onClick={() => {
              void (async () => {
                if (existing) await remove.mutateAsync({ id: existing.id, idea: ideaId });
                onClose();
              })();
            }}
            className="h-[47.5px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[17.5px] text-[16px] text-bd-danger hover:bg-bd-surface-2"
          >
            حذف یادآوری
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={onClose}
            className="h-[47.5px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[19px] text-[16px] text-bd-text hover:bg-bd-surface-2"
          >
            انصراف
          </button>
          <button
            type="button"
            onClick={() => void commit()}
            disabled={!canSave || save.isPending}
            className="h-[47.5px] cursor-pointer rounded-button border-0 bg-bd-accent px-[22.5px] text-[16px] font-semibold text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-50"
          >
            ذخیره
          </button>
        </div>
      </div>
    </Dialog>
  );
}

/**
 * A preview of the next firing, computed in the browser.
 *
 * Only ever shown to the user; the value that actually schedules anything is
 * the one the server calculates when the reminder is saved.
 */
function nextOccurrence(draft: Draft): string | null {
  const now = new Date();
  const today = toJalali(now);

  if (draft.kind === "none") return null;

  if (draft.kind === "exact") {
    return formatJalaliDateWithWeekday(
      jalaliToGregorian({ year: draft.date[0], month: draft.date[1], day: draft.date[2] }),
    );
  }

  const passedToday =
    now.getHours() > draft.hour ||
    (now.getHours() === draft.hour && now.getMinutes() >= draft.minute);

  if (draft.kind === "daily") {
    const day = passedToday ? addJalaliDays(today, 1) : today;
    return formatJalaliDateWithWeekday(jalaliToGregorian(day));
  }

  if (draft.kind === "weekly") {
    if (draft.weekdays.length === 0) return null;
    for (let offset = passedToday ? 1 : 0; offset <= 7; offset += 1) {
      const candidate = addJalaliDays(today, offset);
      if (draft.weekdays.includes(jalaliWeekday(jalaliToGregorian(candidate)))) {
        return formatJalaliDateWithWeekday(jalaliToGregorian(candidate));
      }
    }
    return null;
  }

  // Monthly: this month if the day is still ahead, otherwise the next one,
  // clamped to a month that is too short.
  let { year, month } = today;
  const dayThisMonth = Math.min(draft.dayOfMonth, daysInJalaliMonth(year, month));
  if (dayThisMonth < today.day || (dayThisMonth === today.day && passedToday)) {
    [year, month] = month === 12 ? [year + 1, 1] : [year, month + 1];
  }

  const day = Math.min(draft.dayOfMonth, daysInJalaliMonth(year, month));
  return formatJalaliDate(jalaliToGregorian({ year, month, day }));
}

function addJalaliDays(
  date: { year: number; month: number; day: number },
  days: number,
): { year: number; month: number; day: number } {
  const gregorian = jalaliToGregorian(date);
  gregorian.setUTCDate(gregorian.getUTCDate() + days);
  return toJalali(gregorian);
}
