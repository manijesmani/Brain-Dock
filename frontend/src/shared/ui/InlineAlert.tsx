import { WarningCircleIcon, XIcon } from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

/**
 * What went wrong, said where it went wrong: under the form, beside the
 * button, above the list. Errors are never toasts.
 */
export function InlineAlert({
  children,
  onDismiss,
  revealOnShow = false,
  className = "",
}: {
  children: ReactNode;
  onDismiss?: () => void;
  /** Scrolls itself into view, for a place that may be off screen. */
  revealOnShow?: boolean;
  className?: string;
}) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (revealOnShow) box.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [revealOnShow, children]);

  return (
    <div
      ref={box}
      role="alert"
      className={`flex items-start gap-2 rounded-[9px] bg-bd-danger-bg px-3 py-2 text-[12.5px] leading-[1.8] text-bd-danger ${className}`}
    >
      <WarningCircleIcon size={16} className="mt-[3px] flex-none" />
      <span className="min-w-0 flex-1">{children}</span>
      {onDismiss ? (
        <button
          type="button"
          title="بستن"
          aria-label="بستن پیام"
          onClick={onDismiss}
          className="grid size-6 flex-none cursor-pointer place-items-center rounded-[6px] border-0 bg-transparent text-bd-danger hover:bg-bd-danger-bg"
        >
          <XIcon size={13} />
        </button>
      ) : null}
    </div>
  );
}
