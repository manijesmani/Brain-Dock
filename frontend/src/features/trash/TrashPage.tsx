import { ArrowCounterClockwiseIcon, TrashIcon } from "@phosphor-icons/react";
import { useState } from "react";

import { PageHeader } from "@/features/shell/PageHeader";
import { PageMain } from "@/features/shell/PageMain";
import { useApp } from "@/features/shell/appContext";
import { errorMessage } from "@/shared/api/errors";
import { usePurgeIdea, useTrash, useUntrashIdea } from "@/shared/api/queries";
import { useToast } from "@/shared/hooks/useToast";
import { formatRelativeMoment, toPersianDigits } from "@/shared/lib/persian";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import { CategoryDot, EmptyState } from "@/shared/ui/indicators";
import { Pagination } from "@/shared/ui/Pagination";
import type { TrashedIdea } from "@/types/domain";

const PAGE_SIZE = 20;

/**
 * The deleted ideas, most recent first. Each goes back to where it was, or
 * is deleted for good; nothing leaves the trash on its own.
 */
export function TrashPage() {
  const { categories } = useApp();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const { data, isPending } = useTrash({ page, page_size: PAGE_SIZE });
  const untrash = useUntrashIdea();
  const purge = usePurgeIdea();

  // Why restoring a row failed, shown under that row.
  const [problem, setProblem] = useState<{ id: number; text: string } | null>(null);
  const [purging, setPurging] = useState<TrashedIdea | null>(null);
  const [purgeError, setPurgeError] = useState<string | null>(null);

  const rows = data?.results ?? [];
  const count = data?.pagination.count ?? 0;
  const pages = data?.pagination.pages ?? 1;

  // Emptying the last page of a later one would ask the API for a page past
  // the end, which it answers with a 404, so step back first.
  const leaving = () => {
    if (rows.length === 1 && page > 1) setPage(page - 1);
  };

  const restore = (idea: TrashedIdea) => {
    setProblem(null);
    untrash.mutate(idea.id, {
      onSuccess: () => {
        leaving();
        toast.show("ایده بازگردانده شد");
      },
      onError: (caught) =>
        setProblem({
          id: idea.id,
          text: errorMessage(caught, "بازگردانی ناموفق بود. دوباره امتحان کن."),
        }),
    });
  };

  const deleteForGood = () => {
    if (!purging) return;
    setPurgeError(null);
    purge.mutate(purging.id, {
      onSuccess: () => {
        leaving();
        setPurging(null);
        toast.show("ایده برای همیشه حذف شد");
      },
      onError: (caught) =>
        setPurgeError(errorMessage(caught, "حذف دائمی ناموفق بود. دوباره امتحان کن.")),
    });
  };

  return (
    <PageMain>
      <PageHeader title="سطل زباله" subtitle={`${toPersianDigits(count)} ایده`} />

      <p className="m-0 mb-4 text-[12.5px] leading-[1.8] text-bd-text-3">
        ایده‌های حذف‌شده تا وقتی خودت پاکشان نکنی اینجا می‌مانند و از همین‌جا به جای قبلی‌شان
        برمی‌گردند.
      </p>

      {isPending ? (
        <div className="rounded-card border border-bd-border bg-bd-surface p-14 text-center text-[13.5px] text-bd-text-3 shadow-bd">
          در حال بارگذاری…
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-card border border-bd-border bg-bd-surface shadow-bd">
          <EmptyState padded icon={<TrashIcon size={30} />}>
            سطل زباله خالی است
          </EmptyState>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((idea) => {
            const category = categories.find((item) => item.id === idea.category) ?? null;
            return (
              <div
                key={idea.id}
                className="rounded-card border border-bd-border bg-bd-surface px-4 py-3 shadow-bd @2xl:px-[18px]"
              >
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2.5">
                  <div className="flex min-w-0 flex-[1_1_220px] items-center gap-3">
                    <CategoryDot color={category?.color ?? null} size={9} />
                    <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                      <span className="overflow-hidden text-[13px] font-semibold text-ellipsis whitespace-nowrap @2xl:text-[14px]">
                        {idea.title}
                      </span>
                      <span className="text-[12px] text-bd-text-3">
                        حذف‌شده: {formatRelativeMoment(idea.deleted_at)}
                        {idea.is_archived ? " · از آرشیو" : ""}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-none gap-2 ms-auto">
                    <button
                      type="button"
                      onClick={() => restore(idea)}
                      disabled={untrash.isPending && untrash.variables === idea.id}
                      className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-button border border-bd-border-2 bg-transparent px-3 text-[12.5px] text-bd-text hover:bg-bd-surface-2 disabled:opacity-60 pointer-coarse:h-11"
                    >
                      <ArrowCounterClockwiseIcon size={14} />
                      بازگردانی
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setPurgeError(null);
                        setPurging(idea);
                      }}
                      className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-button border border-bd-border-2 bg-transparent px-3 text-[12.5px] text-bd-danger hover:bg-bd-surface-2 pointer-coarse:h-11"
                    >
                      <TrashIcon size={14} />
                      حذف دائمی
                    </button>
                  </div>
                </div>

                {problem?.id === idea.id ? (
                  <InlineAlert className="mt-2.5" onDismiss={() => setProblem(null)}>
                    {problem.text}
                  </InlineAlert>
                ) : null}
              </div>
            );
          })}
        </div>
      )}

      <Pagination page={page} pages={pages} count={count} pageSize={PAGE_SIZE} onChange={setPage} />

      <ConfirmDialog
        open={purging !== null}
        title="این ایده برای همیشه حذف شود؟"
        confirmLabel="حذف دائمی"
        danger
        pending={purge.isPending}
        error={purgeError}
        onConfirm={deleteForGood}
        onClose={() => {
          setPurging(null);
          setPurgeError(null);
        }}
      >
        <span className="line-clamp-3 font-semibold break-words text-bd-text">
          «{purging?.title}»
        </span>
        <span className="mt-1 block font-semibold text-bd-danger">این کار قابل بازگشت نیست.</span>
        <span className="mt-1 block">متن، عکس‌ها، صدا و یادآوری‌اش هم با آن پاک می‌شود.</span>
      </ConfirmDialog>
    </PageMain>
  );
}
