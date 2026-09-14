import {
  ArchiveIcon,
  ArrowCounterClockwiseIcon,
  ArrowsDownUpIcon,
  BellIcon,
  CaretDownIcon,
  CaretUpIcon,
  LightbulbIcon,
  PaperclipIcon,
  RowsIcon,
  SquaresFourIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { PageHeader } from "@/features/shell/PageHeader";
import { useApp } from "@/features/shell/appContext";
import { useArchiveIdea, useIdeas, useReminders, useTags } from "@/shared/api/queries";
import { daysSince, formatJalaliDate, toPersianDigits } from "@/shared/lib/persian";
import { Dropdown, type DropdownOption } from "@/shared/ui/Dropdown";
import {
  EmptyState,
  PriorityDots,
  StaleBadge,
  StatusDot,
  StatusPill,
} from "@/shared/ui/indicators";
import { Pagination } from "@/shared/ui/Pagination";
import { PRIORITY_LABELS, STATUS_LABELS } from "@/shared/ui/status";
import { Tabs, type TabOption } from "@/shared/ui/Tabs";
import type { IdeaSummary, Reminder } from "@/types/domain";

/** The API's own default, so a page of the table is a page of the listing. */
const PAGE_SIZE = 20;

const STATUS_TABS: TabOption<string>[] = [
  { value: "", label: "همه" },
  { value: "idea", label: STATUS_LABELS.idea },
  { value: "planned", label: STATUS_LABELS.planned },
  { value: "doing", label: STATUS_LABELS.doing },
  { value: "done", label: STATUS_LABELS.done },
];

const PRIORITY_OPTIONS: DropdownOption<string>[] = [
  { value: "", label: "همهٔ اولویت‌ها" },
  { value: "high", label: PRIORITY_LABELS.high },
  { value: "mid", label: PRIORITY_LABELS.mid },
  { value: "low", label: PRIORITY_LABELS.low },
];

const SORT_OPTIONS: DropdownOption<string>[] = [
  { value: "new", label: "تازه‌ترین" },
  { value: "old", label: "قدیمی‌ترین" },
  { value: "touch", label: "آخرین تغییر" },
  { value: "priority", label: "اولویت" },
];

export function BrowsePage({ archived = false }: { archived?: boolean }) {
  const navigate = useNavigate();
  const { categories, selectedCategory, search, user, openReminderDialog } = useApp();

  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [tag, setTag] = useState("");
  const [sort, setSort] = useState("new");
  const [view, setView] = useState<"list" | "card">("list");

  // The archive ignores the sidebar's category, exactly as its listing does.
  const categoryId = archived ? null : selectedCategory;

  // Whatever changes what is listed starts again from page one. The page is
  // stored together with the filters it belongs to, so a number left over from
  // other filters is ignored instead of being reset from an effect.
  const filterKey = JSON.stringify([archived, search, status, priority, tag, sort, categoryId]);
  const [paging, setPaging] = useState({ key: filterKey, page: 1 });
  const page = paging.key === filterKey ? paging.page : 1;
  const goToPage = (next: number) => setPaging({ key: filterKey, page: next });

  const { data: tags = [] } = useTags();
  const { data: reminders = [] } = useReminders();
  const archive = useArchiveIdea();

  const { data, isPending } = useIdeas({
    archived,
    search,
    status: archived ? undefined : status || undefined,
    priority: priority || undefined,
    category: categoryId,
    tag: tag || undefined,
    sort,
    page,
    page_size: PAGE_SIZE,
  });

  const rows = data?.results ?? [];
  const count = data?.pagination.count ?? 0;
  const pages = data?.pagination.pages ?? 1;
  const category = categories.find((item) => item.id === categoryId) ?? null;
  const remindersByIdea = new Map(reminders.map((item) => [item.idea, item]));

  const filtersApplied = Boolean(search || (!archived && status) || priority || tag);
  const emptyText = archived
    ? "آرشیو خالی است"
    : filtersApplied
      ? "ایده‌ای با این فیلترها پیدا نشد"
      : "هنوز ایده‌ای در این دسته ثبت نشده";

  const tagOptions: DropdownOption<string>[] = [
    { value: "", label: "همهٔ تگ‌ها" },
    ...tags.map((item) => ({ value: item.name, label: `#${item.name}` })),
  ];

  const decorate = (idea: IdeaSummary) => ({
    idea,
    category: categories.find((item) => item.id === idea.category) ?? null,
    reminder: remindersByIdea.get(idea.id) ?? null,
    // A stale idea is one still in play that has not moved for long enough,
    // the same rule the API applies to its `stale` filter.
    stale:
      !archived &&
      (idea.status === "idea" || idea.status === "planned") &&
      daysSince(idea.updated_at) >= user.stale_after_days,
  });

  const openIdea = (id: number) => void navigate(ROUTES.note.replace(":ideaId", String(id)));

  // Archiving or restoring the only row of a later page empties that page,
  // and the API answers a page past the end with a 404, so step back first.
  const moveOut = (id: number) => {
    if (rows.length === 1 && page > 1) goToPage(page - 1);
    archive.mutate({ id, restore: archived });
  };

  return (
    <main className="min-w-0 flex-1 px-[47.5px] pt-[32.5px] pb-[137.5px]">
      <PageHeader
        title={archived ? "آرشیو" : (category?.name ?? "همهٔ ایده‌ها")}
        subtitle={`${toPersianDigits(count)} ایده`}
        dot={category?.color}
      />

      <div className="mb-4 flex flex-wrap items-center gap-[11px]">
        {archived ? null : <Tabs value={status} options={STATUS_TABS} onChange={setStatus} />}

        <div className="flex-1" />

        <Dropdown value={priority} options={PRIORITY_OPTIONS} onChange={setPriority} />
        <Dropdown value={tag} options={tagOptions} onChange={setTag} minWidth={200} />
        <Dropdown
          value={sort}
          options={SORT_OPTIONS}
          onChange={setSort}
          minWidth={200}
          icon={<ArrowsDownUpIcon size={17.5} />}
          label={SORT_OPTIONS.find((option) => option.value === sort)?.label}
        />

        <div className="flex gap-[4px] rounded-[11px] bg-bd-surface-2 p-[4px]">
          <ViewToggle active={view === "list"} title="نمای لیست" onClick={() => setView("list")}>
            <RowsIcon size={20} />
          </ViewToggle>
          <ViewToggle active={view === "card"} title="نمای کارت" onClick={() => setView("card")}>
            <SquaresFourIcon size={20} />
          </ViewToggle>
        </div>
      </div>

      {isPending ? (
        <div className="rounded-card border border-bd-border bg-bd-surface p-14 text-center text-[17px] text-bd-text-3 shadow-bd">
          در حال بارگذاری…
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-card border border-bd-border bg-bd-surface shadow-bd">
          <EmptyState
            padded
            icon={archived ? <ArchiveIcon size={37.5} /> : <LightbulbIcon size={37.5} />}
          >
            {emptyText}
          </EmptyState>
        </div>
      ) : view === "list" ? (
        <>
          <TableHeader
            sort={sort}
            onSortDate={() => setSort(sort === "new" ? "old" : "new")}
            onSortPriority={() => setSort("priority")}
          />
          <div className="flex flex-col gap-2">
            {rows.map((row) => (
              <IdeaRow
                key={row.id}
                {...decorate(row)}
                archived={archived}
                onOpen={() => openIdea(row.id)}
                onRemind={() => openReminderDialog(row.id)}
                onMoveOut={() => moveOut(row.id)}
              />
            ))}
          </div>
        </>
      ) : (
        <div className="grid grid-cols-3 gap-4" style={{ opacity: archived ? 0.7 : 1 }}>
          {rows.map((row) => (
            <CardRow
              key={row.id}
              {...decorate(row)}
              archived={archived}
              onOpen={() => openIdea(row.id)}
              onRestore={() => moveOut(row.id)}
            />
          ))}
        </div>
      )}

      <Pagination
        page={page}
        pages={pages}
        count={count}
        pageSize={PAGE_SIZE}
        onChange={goToPage}
      />
    </main>
  );
}

function ViewToggle({
  active,
  title,
  onClick,
  children,
}: {
  active: boolean;
  title: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="grid size-[42.5px] cursor-pointer place-items-center rounded-[9px] border-0"
      style={{
        background: active ? "var(--color-bd-surface-3)" : "transparent",
        color: active ? "var(--color-bd-text)" : "var(--color-bd-text-3)",
      }}
    >
      {children}
    </button>
  );
}

/*
 * The header and every row share one set of column rules: the title takes
 * what is left but never less than its minimum, and the secondary columns give
 * up width together when space runs short, so the columns stay aligned.
 */

function TableHeader({
  sort,
  onSortDate,
  onSortPriority,
}: {
  sort: string;
  onSortDate: () => void;
  onSortPriority: () => void;
}) {
  const dateSorted = sort === "new" || sort === "old";

  return (
    <div className="mb-2.5 flex h-10 items-center gap-4 rounded-card bg-bd-surface-2 px-[22.5px] text-[15px] font-medium text-bd-text-3">
      <span className="min-w-[300px] flex-[1_1_0]">عنوان</span>
      <span className="min-w-0 flex-[0_1_137.5px]">دسته</span>
      <span className="min-w-0 flex-[0_1_162.5px]">وضعیت</span>
      <SortHeader
        title="مرتب‌سازی بر اساس اولویت"
        active={sort === "priority"}
        className="flex-[0_1_80px]"
        onClick={onSortPriority}
        caret={<CaretDownIcon size={14} />}
      >
        اولویت
      </SortHeader>
      <span className="min-w-0 flex-[0_1_162.5px]">یادآوری</span>
      <SortHeader
        title="مرتب‌سازی بر اساس تاریخ"
        active={dateSorted}
        className="flex-[0_1_140px]"
        onClick={onSortDate}
        caret={sort === "old" ? <CaretUpIcon size={14} /> : <CaretDownIcon size={14} />}
      >
        تاریخ
      </SortHeader>
      <span className="w-[85px] flex-none text-left">عملیات</span>
    </div>
  );
}

function SortHeader({
  title,
  active,
  className,
  onClick,
  caret,
  children,
}: {
  title: string;
  active: boolean;
  className: string;
  onClick: () => void;
  caret: ReactNode;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`inline-flex min-w-0 cursor-pointer items-center gap-1 border-0 bg-transparent p-0 text-[15px] font-medium hover:text-bd-text ${
        active ? "text-bd-text" : "text-bd-text-3"
      } ${className}`}
    >
      {children}
      <span className="flex" style={{ opacity: active ? 1 : 0.35 }}>
        {caret}
      </span>
    </button>
  );
}

interface RowProps {
  idea: IdeaSummary;
  category: { name: string; color: string } | null;
  reminder: Reminder | null;
  stale: boolean;
  archived: boolean;
  onOpen: () => void;
}

/**
 * One row of the table, drawn as its own card. `.bd-trow` in index.css lifts
 * it on hover; everything inside reads its colours from the row's `--row-*`
 * variables so the whole row switches to the accent ink at once.
 */
function IdeaRow({
  idea,
  category,
  reminder,
  stale,
  archived,
  onOpen,
  onRemind,
  onMoveOut,
}: RowProps & { onRemind: () => void; onMoveOut: () => void }) {
  const done = idea.status === "done";
  const color = category?.color ?? "var(--color-bd-text-3)";

  return (
    <div
      onClick={onOpen}
      className="bd-trow flex cursor-pointer items-center gap-4 px-[22.5px] py-3"
      style={{ opacity: archived ? 0.7 : done ? 0.62 : 1 }}
    >
      <div className="flex min-w-[300px] flex-[1_1_0] items-center gap-3">
        <span
          className="size-[11px] flex-none rounded-full"
          style={{ background: `var(--row-ink, ${color})` }}
        />
        <div className="flex min-w-0 flex-1 flex-col gap-[4px]">
          <div className="flex min-w-0 items-center gap-2">
            <span
              className="min-w-0 overflow-hidden text-[17.5px] font-semibold text-ellipsis whitespace-nowrap"
              style={{ textDecoration: done ? "line-through" : "none" }}
            >
              {idea.title}
            </span>
            {stale ? <StaleBadge /> : null}
            {idea.has_attachments ? (
              <PaperclipIcon size={17.5} className="flex-none text-(--row-fg-3)" />
            ) : null}
          </div>
          <div className="flex min-w-0 items-center gap-1.5">
            {idea.tags.slice(0, 2).map((name) => (
              <span
                key={name}
                className="inline-flex flex-none items-center gap-[6px] rounded-full bg-(--row-btn) px-2 py-px text-[14px] text-(--row-fg-3)"
              >
                <span
                  className="size-1 rounded-full"
                  style={{ background: `var(--row-ink, ${color})` }}
                />
                {name}
              </span>
            ))}
            <span className="min-w-0 flex-1 overflow-hidden text-[15.5px] text-ellipsis whitespace-nowrap text-(--row-fg-2)">
              {idea.plain_text}
            </span>
          </div>
        </div>
      </div>

      <span className="min-w-0 flex-[0_1_137.5px] overflow-hidden text-[15.5px] text-ellipsis whitespace-nowrap text-(--row-fg-2)">
        {category?.name ?? "بدون دسته"}
      </span>

      <span className="flex min-w-0 flex-[0_1_162.5px]">
        <StatusDot status={idea.status} />
      </span>

      <span className="flex min-w-0 flex-[0_1_80px] items-center">
        <PriorityDots priority={idea.priority} />
      </span>

      <span
        className="flex min-w-0 flex-[0_1_162.5px] items-center gap-[6px] text-[15.5px]"
        style={{ color: "var(--row-ink, var(--color-bd-accent))" }}
      >
        {reminder?.is_active ? (
          <>
            <BellIcon size={16} className="flex-none" />
            <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">
              {reminder.description}
            </span>
          </>
        ) : null}
      </span>

      <span className="min-w-0 flex-[0_1_140px] overflow-hidden text-[15.5px] text-ellipsis whitespace-nowrap text-(--row-fg-3)">
        {formatJalaliDate(idea.created_at)}
      </span>

      <div className="flex w-[85px] flex-none justify-end gap-1.5">
        <RowAction
          title="یادآوری"
          onClick={onRemind}
          color={
            reminder?.is_active ? "var(--row-ink, var(--color-bd-accent))" : "var(--row-btn-fg)"
          }
        >
          <BellIcon size={19} />
        </RowAction>
        {archived ? (
          <RowAction title="بازگردانی" onClick={onMoveOut}>
            <ArrowCounterClockwiseIcon size={19} />
          </RowAction>
        ) : (
          <RowAction title="آرشیو" onClick={onMoveOut}>
            <ArchiveIcon size={19} />
          </RowAction>
        )}
      </div>
    </div>
  );
}

function RowAction({
  title,
  onClick,
  color = "var(--row-btn-fg)",
  children,
}: {
  title: string;
  onClick: () => void;
  color?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={(event) => {
        // The row itself opens the note; its buttons must not.
        event.stopPropagation();
        onClick();
      }}
      className="grid size-[37.5px] cursor-pointer place-items-center rounded-button border-0 bg-(--row-btn) hover:text-(--row-fg)!"
      style={{ color }}
    >
      {children}
    </button>
  );
}

function CardRow({
  idea,
  category,
  reminder,
  stale,
  archived,
  onOpen,
  onRestore,
}: RowProps & { onRestore: () => void }) {
  return (
    <div
      onClick={onOpen}
      className="relative flex min-h-[210px] cursor-pointer flex-col gap-[14px] rounded-card border border-bd-border bg-bd-surface py-[22.5px] ps-[22.5px] pe-[27.5px] shadow-bd hover:border-bd-border-2"
    >
      <span
        className="absolute top-4 bottom-4 w-[4px] rounded-full"
        style={{
          insetInlineEnd: 0,
          background: category?.color ?? "var(--color-bd-text-3)",
        }}
      />

      <div className="flex items-center gap-2">
        <StatusPill status={idea.status} />
        <PriorityDots priority={idea.priority} />
        <div className="flex-1" />
        {stale ? <StaleBadge /> : null}
        {idea.has_attachments ? <PaperclipIcon size={17.5} className="text-bd-text-3" /> : null}
      </div>

      <div className="max-h-11 overflow-hidden text-[18px] leading-[1.5] font-semibold">
        {idea.title}
      </div>
      <div className="max-h-11 flex-1 overflow-hidden text-[15.5px] leading-[1.7] text-bd-text-2">
        {idea.plain_text}
      </div>

      <div className="flex items-center gap-2.5 border-t border-bd-border pt-2.5 text-[15px] text-bd-text-3">
        <span>{category?.name ?? "بدون دسته"}</span>
        <span className="opacity-50">·</span>
        <span>{formatJalaliDate(idea.created_at)}</span>
        <div className="flex-1" />
        {reminder?.is_active ? (
          <span className="inline-flex items-center gap-[6px] text-bd-accent">
            <BellIcon size={16} />
            {reminder.description}
          </span>
        ) : null}
      </div>

      {archived ? (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onRestore();
          }}
          className="inline-flex h-8 cursor-pointer items-center justify-center gap-1.5 rounded-button border border-bd-border-2 bg-transparent text-[15.5px] text-bd-text hover:bg-bd-surface-3"
        >
          <ArrowCounterClockwiseIcon size={16} />
          بازگردانی
        </button>
      ) : null}
    </div>
  );
}
