import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  width: number;
  children: ReactNode;
  /** The reminder dialog scrolls internally; the others do not. */
  scrollable?: boolean;
  /** What a screen reader announces the dialog as. */
  label?: string;
}

/**
 * The dialogs open right now, the most recent last. A confirmation can open
 * over another dialog, and Escape then closes only the one on top.
 */
const openDialogs: object[] = [];

/**
 * The modal shell shared by quick capture, the category editor, the reminder
 * dialog and the confirmations: a dimmed overlay that closes on click or
 * Escape, and a card that animates in.
 */
export function Dialog({ open, onClose, width, children, scrollable = false, label }: DialogProps) {
  const token = useRef({});
  // Read when Escape is pressed rather than subscribed to, so a new function
  // from a re-render does not reopen the dialog at the top of the stack.
  const latestClose = useRef(onClose);
  useEffect(() => {
    latestClose.current = onClose;
  });

  useEffect(() => {
    if (!open) return;

    const self = token.current;
    openDialogs.push(self);

    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape" && openDialogs[openDialogs.length - 1] === self) {
        latestClose.current();
      }
    };
    document.addEventListener("keydown", close);

    // The page behind must not scroll while a dialog is up.
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    return () => {
      openDialogs.splice(openDialogs.indexOf(self), 1);
      document.removeEventListener("keydown", close);
      document.body.style.overflow = overflow;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[1400] grid place-items-center"
      style={{ background: "var(--dialog-overlay-bg, rgba(0,0,0,.55))" }}
    >
      <div className="absolute inset-0" onClick={onClose} />
      {/* The design's width, or the screen's less a margin when that is
          narrower. */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={label}
        className="relative rounded-dialog border border-bd-border bg-bd-surface shadow-bd-lg"
        style={{
          width: `min(${width}px, calc(100vw - 19px))`,
          animation: "bd-in 160ms ease-out",
          maxHeight: scrollable ? "86dvh" : undefined,
          overflowY: scrollable ? "auto" : undefined,
        }}
      >
        {children}
      </div>
    </div>
  );
}
