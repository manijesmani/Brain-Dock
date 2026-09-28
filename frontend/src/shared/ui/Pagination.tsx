import { CaretLeftIcon, CaretRightIcon } from "@phosphor-icons/react";
import type { ReactNode } from "react";

import { toPersianDigits } from "@/shared/lib/persian";

interface PaginationProps {
  page: number;
  pages: number;
  count: number;
  pageSize: number;
  onChange: (page: number) => void;
}

/** At most five page numbers, with null standing for an ellipsis. */
function visiblePages(page: number, pages: number): (number | null)[] {
  if (pages <= 5) return Array.from({ length: pages }, (_, index) => index + 1);
  if (page <= 3) return [1, 2, 3, 4, null, pages];
  if (page >= pages - 2) return [1, null, pages - 3, pages - 2, pages - 1, pages];
  return [1, null, page - 1, page, page + 1, null, pages];
}

/**
 * The summary on the start side and the page numbers on the end side. In a
 * right-to-left layout "previous" points right and "next" points left.
 */
export function Pagination({ page, pages, count, pageSize, onChange }: PaginationProps) {
  if (pages <= 1) return null;

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);

  return (
    // On a phone the summary takes its own line and the numbers sit under it.
    <nav
      aria-label="صفحه‌بندی"
      className="mt-5 flex flex-wrap items-center justify-center gap-1 text-[12.5px] pointer-coarse:gap-2 text-bd-text-3 sm:justify-start"
    >
      <span className="basis-full pb-1 text-center sm:flex-1 sm:basis-auto sm:pb-0 sm:text-start">
        نمایش {toPersianDigits(from)} تا {toPersianDigits(to)} از {toPersianDigits(count)}
      </span>

      <StepButton title="صفحهٔ قبل" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        <CaretRightIcon size={14} />
      </StepButton>

      {visiblePages(page, pages).map((number, index) =>
        number === null ? (
          <span
            key={`gap-${index}`}
            className="grid h-[30px] min-w-[30px] place-items-center text-[13px] pointer-coarse:h-9 pointer-coarse:min-w-9"
          >
            …
          </span>
        ) : (
          <button
            key={number}
            type="button"
            aria-current={number === page ? "page" : undefined}
            disabled={number === page}
            onClick={() => onChange(number)}
            className={`h-[30px] min-w-[30px] rounded-button border-0 bg-transparent px-1.5 text-[13px] pointer-coarse:h-9 pointer-coarse:min-w-9 ${
              number === page
                ? "cursor-default font-bold text-bd-text"
                : "cursor-pointer text-bd-text-3 hover:bg-bd-surface-2"
            }`}
          >
            {toPersianDigits(number)}
          </button>
        ),
      )}

      <StepButton title="صفحهٔ بعد" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        <CaretLeftIcon size={14} />
      </StepButton>
    </nav>
  );
}

function StepButton({
  title,
  disabled,
  onClick,
  children,
}: {
  title: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className="grid size-[30px] cursor-pointer place-items-center rounded-button border-0 bg-transparent text-bd-text-2 pointer-coarse:size-9 hover:bg-bd-surface-2 disabled:cursor-default disabled:opacity-35 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}
