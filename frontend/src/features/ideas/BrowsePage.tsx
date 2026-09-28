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
  TrashIcon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { PageHeader } from "@/features/shell/PageHeader";
import { PageMain } from "@/features/shell/PageMain";
import { useApp } from "@/features/shell/appContext";
import { TrashIdeaDialog } from "@/features/trash/TrashIdeaDialog";
import { errorMessage } from "@/shared/api/errors";
import { useArchiveIdea, useIdeas, useReminders, useTags } from "@/shared/api/queries";
import { useToast } from "@/shared/hooks/useToast";
import { daysSince, formatJalaliDate, toPersianDigits } from "@/shared/lib/persian";
import { Dropdown, type DropdownOption } from "@/shared/ui/Dropdown";
import { InlineAlert } from "@/shared/ui/InlineAlert";
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
  const toast = useToast();
  // What went wrong with a row's button, said above the list.
  const [problem, setProblem] = useState<string | null>(null);
  const [trashing, setTrashing] = useState<IdeaSummary | null>(null);

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

  // Archiving, restoring or deleting the only row of a later page empties
  // that page, and the API answers a page past the end with a 404, so step
  // back first.
  const leaving = () => {
    if (rows.length === 1 && page > 1) goToPage(page - 1);
  };

  const moveOut = (id: number) => {
    setProblem(null);
    archive.mutate(
      { id, restore: archived },
      {
        onSuccess: () => {
          leaving();
          toast.show(archived ? "ایده از آرشیو خارج شد" : "ایده آرشیو شد");
        },
        onError: (caught) =>
          setProblem(
            errorMessage(
              caught,
              archived
                ? "خارج کردن از آرشیو ناموفق بود. دوباره امتحان کن."
                : "آرشیو کردن ناموفق بود. دوباره امتحان کن.",
            ),
          ),
      },
    );
  };

  return (
    <PageMain>
      <PageHeader
        title={archived ? "آرشیو" : (category?.name ?? "همهٔ ایده‌ها")}
        subtitle={`${toPersianDigits(count)} ایده`}
        dot={category?.color}
      />

      {/* Where the tabs and the filters do not fit on one line, the tabs take
          a line of their own (scrolling sideways on a phone) and the filters
          wrap onto the lines below. */}
      <div className="mb-4 flex flex-wrap items-center gap-[9px]">
        {archived ? null : (
          <div className="w-full min-w-0 @5xl:w-auto">
            <Tabs value={status} options={STATUS_TABS} onChange={setStatus} />
          </div>
        )}

        <div className="hidden flex-1 @5xl:block" />

        <Dropdown value={priority} options={PRIORITY_OPTIONS} onChange={setPriority} />
        <Dropdown value={tag} options={tagOptions} onChange={setTag} minWidth={160} />
        <Dropdown
          value={sort}
          options={SORT_OPTIONS}
          onChange={setSort}
          minWidth={160}
          icon={<ArrowsDownUpIcon size={14} />}
          label={SORT_OPTIONS.find((option) => option.value === sort)?.label}
        />

        <div className="flex gap-[3px] rounded-[9px] bg-bd-surface-2 p-[3px]">
          <ViewToggle active={view === "list"} title="نمای لیست" onClick={() => setView("list")}>
            <RowsIcon size={16} />
          </ViewToggle>
          <ViewToggle active={view === "card"} title="نمای کارت" onClick={() => setView("card")}>
            <SquaresFourIcon size={16} />
          </ViewToggle>
        </div>
      </div>

      {problem ? (
        <InlineAlert className="mb-3" onDismiss={() => setProblem(null)}>
          {problem}
        </InlineAlert>
      ) : null}

      {isPending ? (
        <div className="rounded-card border border-bd-border bg-bd-surface p-14 text-center text-[13.5px] text-bd-text-3 shadow-bd">
          در حال بارگذاری…
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-card border border-bd-border bg-bd-surface shadow-bd">
          <EmptyState
            padded
            icon={archived ? <ArchiveIcon size={30} /> : <LightbulbIcon size={30} />}
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
                onTrash={() => {
                  setProblem(null);
                  setTrashing(row);
                }}
              />
            ))}
          </div>
        </>
      ) : (
        <div
          className="grid grid-cols-1 gap-4 @xl:grid-cols-2 @4xl:grid-cols-3"
          style={{ opacity: archived ? 0.7 : 1 }}
        >
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

      <TrashIdeaDialog idea={trashing} onClose={() => setTrashing(null)} onTrashed={leaving} />
    </PageMain>
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
      className="grid size-[34px] cursor-pointer place-items-center rounded-[7px] border-0 pointer-coarse:size-11"
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
 *
 * Which columns exist at all follows the width the table is given (the
 * @-variants are container queries on PageMain), so the sidebar being open or
 * collapsed counts as much as the size of the window:
 *   below 42rem   no table: each row is a card with a line of details
 *   42rem         title, status, date
 *   48rem         + category, priority
 *   56rem         + reminder
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
    <div className="mb-2.5 hidden h-10 items-center gap-4 rounded-card bg-bd-surface-2 px-[18px] text-[12px] font-medium text-bd-text-3 @2xl:flex">
      <span className="min-w-[240px] flex-[1_1_0]">عنوان</span>
      <span className="hidden min-w-0 flex-[0_1_137.5px] @3xl:block">دسته</span>
      <span className="min-w-0 flex-[0_1_162.5px]">وضعیت</span>
      <SortHeader
        title="مرتب‌سازی بر اساس اولویت"
        active={sort === "priority"}
        className="hidden flex-[0_1_80px] @3xl:inline-flex"
        onClick={onSortPriority}
        caret={<CaretDownIcon size={11} />}
      >
        اولویت
      </SortHeader>
      <span className="hidden min-w-0 flex-[0_1_162.5px] @4xl:block">یادآوری</span>
      <SortHeader
        title="مرتب‌سازی بر اساس تاریخ"
        active={dateSorted}
        className="inline-flex flex-[0_1_140px]"
        onClick={onSortDate}
        caret={sort === "old" ? <CaretUpIcon size={11} /> : <CaretDownIcon size={11} />}
      >
        تاریخ
      </SortHeader>
      <span className="w-[102px] flex-none text-left pointer-coarse:w-[124px]">عملیات</span>
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
      className={`min-w-0 cursor-pointer items-center gap-1 border-0 bg-transparent p-0 text-[12px] font-medium hover:text-bd-text ${
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
  onTrash,
}: RowProps & { onRemind: () => void; onMoveOut: () => void; onTrash: () => void }) {
  const done = idea.status === "done";
  const color = category?.color ?? "var(--color-bd-text-3)";

  return (
    <div
      onClick={onOpen}
      className="bd-trow flex cursor-pointer items-center gap-3 px-4 py-3 @2xl:gap-4 @2xl:px-[18px]"
      style={{ opacity: archived ? 0.7 : done ? 0.62 : 1 }}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3 @2xl:min-w-[240px] @2xl:flex-[1_1_0]">
        <span
          className="size-[9px] flex-none rounded-full"
          style={{ background: `var(--row-ink, ${color})` }}
        />
        <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <div className="flex min-w-0 items-center gap-2">
            <span
              className="min-w-0 overflow-hidden text-[13px] font-semibold text-ellipsis whitespace-nowrap @2xl:text-[14px]"
              style={{ textDecoration: done ? "line-through" : "none" }}
            >
              {idea.title}
            </span>
            {stale ? <StaleBadge /> : null}
            {idea.has_attachments ? (
              <PaperclipIcon size={14} className="flex-none text-(--row-fg-3)" />
            ) : null}
          </div>
          <div className="flex min-w-0 items-center gap-1.5">
            {idea.tags.slice(0, 2).map((name) => (
              <span
                key={name}
                className="inline-flex flex-none items-center gap-[5px] rounded-full bg-(--row-btn) px-2 py-px text-[11px] text-(--row-fg-3)"
              >
                <span
                  className="size-1 rounded-full"
                  style={{ background: `var(--row-ink, ${color})` }}
                />
                {name}
              </span>
            ))}
            <span className="min-w-0 flex-1 overflow-hidden text-[12.5px] text-ellipsis whitespace-nowrap text-(--row-fg-2)">
              {idea.plain_text}
            </span>
          </div>

          {/* The columns the table has no room for, as one line of details. */}
          <div className="flex min-w-0 items-center gap-2.5 text-[11.5px] text-(--row-fg-3) @2xl:hidden">
            <span className="flex min-w-0 flex-none">
              <StatusDot status={idea.status} />
            </span>
            <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">
              {category?.name ?? "بدون دسته"}
            </span>
            {reminder?.is_active ? (
              <BellIcon
                size={12}
                className="flex-none"
                style={{ color: "var(--row-ink, var(--color-bd-accent))" }}
              />
            ) : null}
          </div>
        </div>
      </div>

      <span className="hidden min-w-0 flex-[0_1_137.5px] overflow-hidden text-[12.5px] text-ellipsis whitespace-nowrap text-(--row-fg-2) @3xl:block">
        {category?.name ?? "بدون دسته"}
      </span>

      <span className="hidden min-w-0 flex-[0_1_162.5px] @2xl:flex">
        <StatusDot status={idea.status} />
      </span>

      <span className="hidden min-w-0 flex-[0_1_80px] items-center @3xl:flex">
        <PriorityDots priority={idea.priority} />
      </span>

      <span
        className="hidden min-w-0 flex-[0_1_162.5px] items-center gap-[5px] text-[12.5px] @4xl:flex"
        style={{ color: "var(--row-ink, var(--color-bd-accent))" }}
      >
        {reminder?.is_active ? (
          <>
            <BellIcon size={13} className="flex-none" />
            <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">
              {reminder.description}
            </span>
          </>
        ) : null}
      </span>

      <span className="hidden min-w-0 flex-[0_1_140px] overflow-hidden text-[12.5px] text-ellipsis whitespace-nowrap text-(--row-fg-3) @2xl:block">
        {formatJalaliDate(idea.created_at)}
      </span>

      {/* Always shown, on a phone too: nothing here waits for a hover. */}
      <div className="flex flex-none justify-end gap-1.5 @2xl:w-[102px] pointer-coarse:gap-2 pointer-coarse:@2xl:w-[124px]">
        <RowAction
          title="یادآوری"
          onClick={onRemind}
          color={
            reminder?.is_active ? "var(--row-ink, var(--color-bd-accent))" : "var(--row-btn-fg)"
          }
        >
          <BellIcon size={15} />
        </RowAction>
        {archived ? (
          <RowAction title="بازگردانی" onClick={onMoveOut}>
            <ArrowCounterClockwiseIcon size={15} />
          </RowAction>
        ) : (
          <RowAction title="آرشیو" onClick={onMoveOut}>
            <ArchiveIcon size={15} />
          </RowAction>
        )}
        <RowAction title="حذف" label="حذف ایده" onClick={onTrash} danger>
          <TrashIcon size={15} />
        </RowAction>
      </div>
    </div>
  );
}

function RowAction({
  title,
  label = title,
  onClick,
  color = "var(--row-btn-fg)",
  danger = false,
  children,
}: {
  title: string;
  /** What a screen reader says, when the tooltip alone is too terse. */
  label?: string;
  onClick: () => void;
  color?: string;
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={label}
      onClick={(event) => {
        // The row itself opens the note; its buttons must not.
        event.stopPropagation();
        onClick();
      }}
      className={`grid size-[30px] cursor-pointer place-items-center rounded-button border-0 bg-(--row-btn) pointer-coarse:size-9 ${
        danger ? "hover:text-bd-danger!" : "hover:text-(--row-fg)!"
      }`}
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
      className="relative flex min-h-[168px] cursor-pointer flex-col gap-[11px] rounded-card border border-bd-border bg-bd-surface py-[18px] ps-[18px] pe-[22px] shadow-bd hover:border-bd-border-2"
    >
      <span
        className="absolute top-4 bottom-4 w-[3px] rounded-full"
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
        {idea.has_attachments ? <PaperclipIcon size={14} className="text-bd-text-3" /> : null}
      </div>

      <div className="max-h-11 overflow-hidden text-[14.5px] leading-[1.5] font-semibold">
        {idea.title}
      </div>
      <div className="max-h-11 flex-1 overflow-hidden text-[12.5px] leading-[1.7] text-bd-text-2">
        {idea.plain_text}
      </div>

      <div className="flex items-center gap-2.5 border-t border-bd-border pt-2.5 text-[12px] text-bd-text-3">
        <span>{category?.name ?? "بدون دسته"}</span>
        <span className="opacity-50">·</span>
        <span>{formatJalaliDate(idea.created_at)}</span>
        <div className="flex-1" />
        {reminder?.is_active ? (
          <span className="inline-flex items-center gap-[5px] text-bd-accent">
            <BellIcon size={13} />
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
          className="inline-flex h-8 cursor-pointer items-center justify-center gap-1.5 rounded-button border border-bd-border-2 bg-transparent text-[12.5px] text-bd-text hover:bg-bd-surface-3"
        >
          <ArrowCounterClockwiseIcon size={13} />
          بازگردانی
        </button>
      ) : null}
    </div>
  );
}
