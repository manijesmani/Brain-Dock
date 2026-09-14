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
    <nav
      aria-label="صفحه‌بندی"
      className="mt-5 flex items-center gap-1 text-[15.5px] text-bd-text-3"
    >
      <span className="flex-1">
        نمایش {toPersianDigits(from)} تا {toPersianDigits(to)} از {toPersianDigits(count)}
      </span>

      <StepButton title="صفحهٔ قبل" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        <CaretRightIcon size={17.5} />
      </StepButton>

      {visiblePages(page, pages).map((number, index) =>
        number === null ? (
          <span
            key={`gap-${index}`}
            className="grid h-[37.5px] min-w-[37.5px] place-items-center text-[16px]"
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
            className={`h-[37.5px] min-w-[37.5px] rounded-button border-0 bg-transparent px-1.5 text-[16px] ${
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
        <CaretLeftIcon size={17.5} />
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
      className="grid size-[37.5px] cursor-pointer place-items-center rounded-button border-0 bg-transparent text-bd-text-2 hover:bg-bd-surface-2 disabled:cursor-default disabled:opacity-35 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}
