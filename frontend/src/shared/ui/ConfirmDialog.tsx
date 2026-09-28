import type { ReactNode } from "react";
import { useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { Dialog } from "@/shared/ui/Dialog";
import { InlineAlert } from "@/shared/ui/InlineAlert";

interface ConfirmDialogProps {
  open: boolean;
  /** The question, such as «آیا از حذف این ایده مطمئن هستید؟». */
  title: string;
  /** What it concerns and what follows: the idea's title, a warning. */
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  /** Red, for what removes something. */
  danger?: boolean;
  /** While the request runs: the confirm button is off, so it is sent once. */
  pending?: boolean;
  /** Why the last attempt failed, shown above the buttons. */
  error?: string | null;
  onConfirm: () => void;
  onClose: () => void;
}

/**
 * Asks before something is done. Escape, a click outside and «انصراف» all
 * leave everything as it was; the cancel button is the one focused, so a
 * stray Enter never confirms.
 *
 * Rendered into the page's body, so it can open over another dialog -- the
 * user panel -- and still cover the whole screen.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  cancelLabel = "انصراف",
  danger = false,
  pending = false,
  error = null,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const cancel = useRef<HTMLButtonElement>(null);

  // Focus starts on «انصراف», and goes back to the button that opened the
  // dialog once it closes -- when that button is still there.
  useLayoutEffect(() => {
    if (!open) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancel.current?.focus();
    return () => {
      if (opener?.isConnected) opener.focus();
    };
  }, [open]);

  // A request already on its way cannot be called back; the dialog waits for it.
  const close = () => {
    if (!pending) onClose();
  };

  return createPortal(
    <Dialog open={open} onClose={close} width={400} label={title}>
      <div className="p-5">
        <h2 className="m-0 text-[15px] leading-[1.7] font-semibold">{title}</h2>
        {children ? (
          <div className="mt-2 text-[13px] leading-[1.8] text-bd-text-2">{children}</div>
        ) : null}

        {error ? <InlineAlert className="mt-3.5">{error}</InlineAlert> : null}

        <div className="mt-5 flex flex-wrap justify-end gap-[9px]">
          <button
            ref={cancel}
            type="button"
            onClick={close}
            disabled={pending}
            className="h-[38px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[15px] text-[13px] text-bd-text hover:bg-bd-surface-2 disabled:cursor-default disabled:opacity-60 pointer-coarse:h-11"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className={`h-[38px] cursor-pointer rounded-button border-0 px-[15px] text-[13px] font-semibold disabled:cursor-default disabled:opacity-60 pointer-coarse:h-11 ${
              danger
                ? "bg-bd-danger-solid text-white hover:bg-bd-danger-solid-hover"
                : "bg-bd-accent text-bd-accent-ink hover:bg-bd-accent-hover"
            }`}
          >
            {pending ? "در حال انجام…" : confirmLabel}
          </button>
        </div>
      </div>
    </Dialog>,
    document.body,
  );
}
