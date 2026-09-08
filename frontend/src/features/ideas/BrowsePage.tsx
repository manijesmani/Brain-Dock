import {
  ArchiveIcon,
  ArrowCounterClockwiseIcon,
  ArrowsDownUpIcon,
  BellIcon,
  LightbulbIcon,
  MagnifyingGlassIcon,
  PaperclipIcon,
  RowsIcon,
  SquaresFourIcon,
} from "@phosphor-icons/react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { useApp } from "@/features/shell/appContext";
import { useArchiveIdea, useIdeas, useReminders, useTags } from "@/shared/api/queries";
import { daysSince, formatJalaliDate, toPersianDigits } from "@/shared/lib/persian";
import { Dropdown, type DropdownOption } from "@/shared/ui/Dropdown";
import { Input } from "@/shared/ui/Input";
import {
  CategoryDot,
  EmptyState,
  PriorityDots,
  StaleBadge,
  StatusPill,
} from "@/shared/ui/indicators";
import { PRIORITY_LABELS, STATUS_LABELS } from "@/shared/ui/status";
import type { IdeaSummary, Reminder } from "@/types/domain";

const STATUS_OPTIONS: DropdownOption<string>[] = [
  { value: "", label: "همهٔ وضعیت‌ها" },
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
  const { categories, selectedCategory, search, setSearch, user } = useApp();

  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [tag, setTag] = useState("");
  const [sort, setSort] = useState("new");
  const [view, setView] = useState<"list" | "card">("list");

  const { data: tags = [] } = useTags();
  const { data: reminders = [] } = useReminders();
  const restore = useArchiveIdea();

  const { data, isPending } = useIdeas({
    archived,
    search,
    status: status || undefined,
    priority: priority || undefined,
    category: archived ? undefined : selectedCategory,
    tag: tag || undefined,
    sort,
    page_size: 50,
  });

  const rows = data?.results ?? [];
  const category = categories.find((item) => item.id === selectedCategory) ?? null;
  const remindersByIdea = new Map(reminders.map((item) => [item.idea, item]));

  const filtersApplied = Boolean(search || status || priority || tag);
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

  return (
    <main className="min-w-0 flex-1 px-[38px] pt-[30px] pb-[110px]">
      <header className="mb-[18px] flex items-center gap-3">
        {category && !archived ? <CategoryDot color={category.color} size={10} /> : null}
        <h1 className="m-0 text-[22px] font-bold tracking-tight">
          {archived ? "آرشیو" : (category?.name ?? "همهٔ ایده‌ها")}
        </h1>
        <span className="text-[12.5px] text-bd-text-3">
          {toPersianDigits(data?.pagination.count ?? 0)} ایده
        </span>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-[9px]">
        <div className="w-[270px]">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="جستجو در ایده‌ها…"
            trailingIcon={<MagnifyingGlassIcon size={16} />}
          />
        </div>

        <Dropdown value={status} options={STATUS_OPTIONS} onChange={setStatus} minWidth={190} />
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

        <div className="flex-1" />

        <div className="flex gap-[3px] rounded-[9px] bg-bd-surface-2 p-[3px]">
          <ViewToggle active={view === "list"} title="نمای لیست" onClick={() => setView("list")}>
            <RowsIcon size={16} />
          </ViewToggle>
          <ViewToggle active={view === "card"} title="نمای کارت" onClick={() => setView("card")}>
            <SquaresFourIcon size={16} />
          </ViewToggle>
        </div>
      </div>

      {isPending ? (
        <div className="rounded-card border border-bd-border bg-bd-surface p-14 text-center text-[13.5px] text-bd-text-3 shadow-bd">
          در حال بارگذاری…
        </div>
      ) : view === "list" ? (
        <div
          className="rounded-card border border-bd-border bg-bd-surface shadow-bd"
          style={{ opacity: archived ? 0.7 : 1 }}
        >
          {rows.length === 0 ? (
            <EmptyState
              padded
              icon={archived ? <ArchiveIcon size={30} /> : <LightbulbIcon size={30} />}
            >
              {emptyText}
            </EmptyState>
          ) : (
            rows.map((row, index) => (
              <ListRow
                key={row.id}
                {...decorate(row)}
                first={index === 0}
                archived={archived}
                onOpen={() => void navigate(ROUTES.note.replace(":ideaId", String(row.id)))}
                onRestore={() => restore.mutate({ id: row.id, restore: true })}
              />
            ))
          )}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-card border border-bd-border bg-bd-surface">
          <EmptyState
            padded
            icon={archived ? <ArchiveIcon size={30} /> : <LightbulbIcon size={30} />}
          >
            {emptyText}
          </EmptyState>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4" style={{ opacity: archived ? 0.7 : 1 }}>
          {rows.map((row) => (
            <CardRow
              key={row.id}
              {...decorate(row)}
              archived={archived}
              onOpen={() => void navigate(ROUTES.note.replace(":ideaId", String(row.id)))}
              onRestore={() => restore.mutate({ id: row.id, restore: true })}
            />
          ))}
        </div>
      )}
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
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="grid size-[34px] cursor-pointer place-items-center rounded-[7px] border-0"
      style={{
        background: active ? "var(--color-bd-surface-3)" : "transparent",
        color: active ? "var(--color-bd-text)" : "var(--color-bd-text-3)",
      }}
    >
      {children}
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
  onRestore: () => void;
}

function ListRow({
  idea,
  category,
  reminder,
  stale,
  first,
  archived,
  onOpen,
  onRestore,
}: RowProps & { first: boolean }) {
  const done = idea.status === "done";

  return (
    <div
      onClick={onOpen}
      className="relative flex cursor-pointer items-center gap-4 py-[13px] ps-[18px] pe-[22px] hover:bg-bd-surface-2"
      style={{
        borderTop: first ? "0" : "1px solid var(--color-bd-border)",
        opacity: done ? 0.62 : 1,
      }}
    >
      <span
        className="absolute top-[9px] bottom-[9px] w-[3px] rounded-full"
        style={{
          insetInlineEnd: 0,
          background: category?.color ?? "var(--color-bd-text-3)",
        }}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className="overflow-hidden text-[14px] font-semibold text-ellipsis whitespace-nowrap"
            style={{ textDecoration: done ? "line-through" : "none" }}
          >
            {idea.title}
          </span>
          {idea.tags.slice(0, 2).map((name) => (
            <span
              key={name}
              className="inline-flex flex-none items-center gap-[5px] rounded-full bg-bd-surface-2 px-2 py-px text-[11px] text-bd-text-3"
            >
              <span
                className="size-1 rounded-full"
                style={{ background: category?.color ?? "var(--color-bd-text-3)" }}
              />
              {name}
            </span>
          ))}
          {stale ? <StaleBadge /> : null}
          {idea.has_attachments ? (
            <PaperclipIcon size={14} className="flex-none text-bd-text-3" />
          ) : null}
        </div>
        <div className="overflow-hidden text-[12.5px] text-ellipsis whitespace-nowrap text-bd-text-2">
          {idea.plain_text}
        </div>
      </div>

      <StatusPill status={idea.status} />
      <PriorityDots priority={idea.priority} />

      <span className="w-[110px] flex-none overflow-hidden text-[12.5px] text-ellipsis whitespace-nowrap text-bd-text-2">
        {category?.name ?? "بدون دسته"}
      </span>

      <span className="inline-flex w-[130px] flex-none items-center gap-[5px] text-[12.5px] text-bd-accent">
        {reminder?.is_active ? (
          <>
            <BellIcon size={13} />
            {reminder.description}
          </>
        ) : null}
      </span>

      <span className="w-[112px] flex-none text-left text-[12.5px] text-bd-text-3">
        {formatJalaliDate(idea.created_at)}
      </span>

      {archived ? (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onRestore();
          }}
          className="inline-flex h-[30px] flex-none cursor-pointer items-center gap-1.5 rounded-button border border-bd-border-2 bg-transparent px-[11px] text-[12.5px] text-bd-text hover:bg-bd-surface-3"
        >
          <ArrowCounterClockwiseIcon size={13} />
          بازگردانی
        </button>
      ) : null}
    </div>
  );
}

function CardRow({ idea, category, reminder, stale, archived, onOpen, onRestore }: RowProps) {
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
