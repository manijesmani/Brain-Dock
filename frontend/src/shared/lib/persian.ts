/**
 * Persian presentation helpers.
 *
 * The API speaks UTC and ASCII digits. Everything the user reads is converted
 * here, at the last moment before it reaches the screen -- the same division
 * the backend keeps in core/formatting.py.
 */

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

export const JALALI_MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
] as const;

/** Saturday first, matching jdatetime and the reminder dialog's chips. */
export const JALALI_WEEKDAYS = [
  "شنبه",
  "یکشنبه",
  "دوشنبه",
  "سه‌شنبه",
  "چهارشنبه",
  "پنجشنبه",
  "جمعه",
] as const;

export const TEHRAN = "Asia/Tehran";

export function toPersianDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (digit) => PERSIAN_DIGITS[Number(digit)] ?? digit);
}

export interface JalaliDate {
  year: number;
  month: number;
  day: number;
}

/**
 * Converts an instant to the Jalali calendar in Tehran.
 *
 * `Intl` with the `persian` calendar does the arithmetic, so no conversion
 * table is shipped and the result agrees with the server, which uses
 * jdatetime over the same algorithm.
 */
export function toJalali(value: Date | string): JalaliDate {
  const date = typeof value === "string" ? new Date(value) : value;

  const parts = new Intl.DateTimeFormat("en-u-ca-persian-nu-latn", {
    timeZone: TEHRAN,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(date);

  const read = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);

  return { year: read("year"), month: read("month"), day: read("day") };
}

/** Weekday index with Saturday at 0. */
export function jalaliWeekday(value: Date | string): number {
  const date = typeof value === "string" ? new Date(value) : value;
  const local = new Date(date.toLocaleString("en-US", { timeZone: TEHRAN }));
  // JavaScript counts Sunday as 0; Saturday is 6 there and 0 here.
  return (local.getDay() + 1) % 7;
}

export function isJalaliLeapYear(year: number): boolean {
  return [1, 5, 9, 13, 17, 22, 26, 30].includes(year % 33);
}

export function daysInJalaliMonth(year: number, month: number): number {
  if (month <= 6) return 31;
  if (month <= 11) return 30;
  return isJalaliLeapYear(year) ? 30 : 29;
}

/** Converts a Jalali date to the Gregorian one, for sending to the API. */
export function jalaliToGregorian({ year, month, day }: JalaliDate): Date {
  // Days elapsed since the Jalali epoch, then mapped onto the Gregorian one.
  const jy = year - 979;
  const jm = month - 1;
  const jd = day - 1;

  let dayCount = 365 * jy + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4) + 78 + jd;
  dayCount += jm < 7 ? jm * 31 : jm * 30 + 6;

  let gy = 1600 + 400 * Math.floor(dayCount / 146097);
  let remaining = dayCount % 146097;

  if (remaining >= 36525) {
    remaining -= 1;
    gy += 100 * Math.floor(remaining / 36524);
    remaining %= 36524;
    if (remaining >= 365) remaining += 1;
  }

  gy += 4 * Math.floor(remaining / 1461);
  remaining %= 1461;

  if (remaining >= 366) {
    remaining -= 1;
    gy += Math.floor(remaining / 365);
    remaining %= 365;
  }

  const leap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0;
  const monthLengths = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

  let gm = 0;
  for (;;) {
    const length = monthLengths[gm];
    if (gm >= 12 || length === undefined || remaining < length) break;
    remaining -= length;
    gm += 1;
  }

  return new Date(Date.UTC(gy, gm, remaining + 1, 12));
}

export function formatJalaliDate(value: Date | string): string {
  const { year, month, day } = toJalali(value);
  return `${toPersianDigits(day)} ${JALALI_MONTHS[month - 1] ?? ""} ${toPersianDigits(year)}`;
}

export function formatJalaliWeekday(value: Date | string): string {
  return JALALI_WEEKDAYS[jalaliWeekday(value)] ?? "";
}

export function formatJalaliDateWithWeekday(value: Date | string): string {
  return `${formatJalaliWeekday(value)} ${formatJalaliDate(value)}`;
}

export function formatClock(hour: number, minute: number): string {
  return `${toPersianDigits(hour)}:${toPersianDigits(String(minute).padStart(2, "0"))}`;
}

export function formatTimeOfDay(value: Date | string): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: TEHRAN,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);

  const read = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);

  return formatClock(read("hour"), read("minute"));
}

/**
 * Relative wording for the notification centre: today and yesterday are named
 * rather than dated, which is how the design writes them.
 */
export function formatRelativeMoment(value: Date | string): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const today = toJalali(new Date());
  const then = toJalali(date);
  const clock = `ساعت ${formatTimeOfDay(date)}`;

  if (then.year === today.year && then.month === today.month && then.day === today.day) {
    return `امروز، ${clock}`;
  }

  const yesterday = toJalali(new Date(Date.now() - 86_400_000));
  if (
    then.year === yesterday.year &&
    then.month === yesterday.month &&
    then.day === yesterday.day
  ) {
    return `دیروز، ${clock}`;
  }

  return `${formatJalaliDate(date)}، ${clock}`;
}

/** Whole days between an instant and now, counted on Tehran calendar days. */
export function daysSince(value: Date | string): number {
  const date = typeof value === "string" ? new Date(value) : value;
  const startOfDay = (input: Date) =>
    new Date(input.toLocaleDateString("en-US", { timeZone: TEHRAN }));

  const diff = startOfDay(new Date()).getTime() - startOfDay(date).getTime();
  return Math.max(0, Math.round(diff / 86_400_000));
}
