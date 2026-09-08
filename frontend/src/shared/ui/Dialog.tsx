import type { ReactNode } from "react";
import { useEffect } from "react";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  width: number;
  children: ReactNode;
  /** The reminder dialog scrolls internally; the others do not. */
  scrollable?: boolean;
}

/**
 * The modal shell shared by quick capture, the category editor and the
 * reminder dialog: a dimmed overlay that closes on click or Escape, and a
 * card that animates in.
 */
export function Dialog({ open, onClose, width, children, scrollable = false }: DialogProps) {
  useEffect(() => {
    if (!open) return;

    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", close);

    // The page behind must not scroll while a dialog is up.
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", close);
      document.body.style.overflow = overflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[1400] grid place-items-center"
      style={{ background: "var(--dialog-overlay-bg, rgba(0,0,0,.55))" }}
    >
      <div className="absolute inset-0" onClick={onClose} />
      <div
        className="relative rounded-dialog border border-bd-border bg-bd-surface shadow-bd-lg"
        style={{
          width,
          animation: "bd-in 160ms ease-out",
          maxHeight: scrollable ? "86vh" : undefined,
          overflowY: scrollable ? "auto" : undefined,
        }}
      >
        {children}
      </div>
    </div>
  );
}
