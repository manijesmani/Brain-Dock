import { CheckCircleIcon, WarningCircleIcon } from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { errorMessage } from "@/shared/api/errors";
import { type ToastAction, type ToastApi, ToastContext } from "@/shared/hooks/useToast";

interface ToastItem {
  id: number;
  key?: string;
  message: string;
  action?: ToastAction;
  duration: number;
}

/** How long a toast stays: longer when it has a button to reach for. */
const DURATION = 3000;
const ACTION_DURATION = 5000;
/** How long a toast whose action failed stays, to be read and tried again. */
const FAILURE_DURATION = 6000;
const FADE = 300;

/** Toasts on screen at once; an older one gives way to a newer one. */
const LIMIT = 3;

/**
 * Hosts the toasts for everything inside it.
 *
 * They stack at the foot of the screen, one above another, above the home
 * indicator's safe area and, with `raised`, above the note editor's toolbar.
 * The round capture button keeps its corner: on a phone the toasts only stay
 * clear of that side, which leaves them room for a line of text and a
 * button; on a wider screen they sit centred. A toast without a button
 * ignores touches entirely, so it never stands between a finger and a button
 * underneath.
 */
export function ToastProvider({
  children,
  raised = false,
}: {
  children: ReactNode;
  raised?: boolean;
}) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const show = useCallback<ToastApi["show"]>((message, { duration, action, key } = {}) => {
    const item: ToastItem = {
      id: ++nextId.current,
      key,
      message,
      action,
      duration: duration ?? (action ? ACTION_DURATION : DURATION),
    };
    setItems((current) => {
      const others = key ? current.filter((existing) => existing.key !== key) : current;
      return [...others.slice(-(LIMIT - 1)), item];
    });
  }, []);

  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 z-[1500] flex flex-col items-center gap-2 pr-4 pl-[88px] sm:px-[88px] lg:px-[98px]"
        style={{
          // 53px is the editor toolbar's height.
          bottom: `calc(${raised ? 53 : 0}px + 16px + env(safe-area-inset-bottom, 0px))`,
        }}
      >
        {items.map((item) => (
          <Toast key={item.id} item={item} onGone={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function Toast({ item, onGone }: { item: ToastItem; onGone: (id: number) => void }) {
  const [leaving, setLeaving] = useState(false);
  // Held while a pointer or the keyboard is on it, so it does not slip away
  // from under the finger about to press its button.
  const [held, setHeld] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const remaining = useRef(item.duration);

  useEffect(() => {
    if (held || busy || leaving) return;
    const started = Date.now();
    const timer = window.setTimeout(() => setLeaving(true), remaining.current);
    return () => {
      window.clearTimeout(timer);
      remaining.current -= Date.now() - started;
    };
  }, [held, busy, leaving]);

  useEffect(() => {
    if (!leaving) return;
    const timer = window.setTimeout(() => onGone(item.id), FADE);
    return () => window.clearTimeout(timer);
  }, [leaving, onGone, item.id]);

  const act = async (action: ToastAction) => {
    setBusy(true);
    setFailure(null);
    try {
      await action.run();
      onGone(item.id);
    } catch (caught) {
      // Said here, where it was pressed, and left up long enough to try again.
      setFailure(errorMessage(caught, action.failure ?? "انجام نشد. دوباره امتحان کن."));
      remaining.current = FAILURE_DURATION;
      setBusy(false);
    }
  };

  const Icon = failure ? WarningCircleIcon : CheckCircleIcon;

  return (
    <div
      onPointerEnter={() => setHeld(true)}
      onPointerLeave={() => setHeld(false)}
      onFocus={() => setHeld(true)}
      onBlur={() => setHeld(false)}
      className={`flex max-w-[min(440px,100%)] items-center gap-2 rounded-card border border-bd-border bg-bd-surface py-2 ps-3.5 text-[13px] leading-[1.7] font-medium text-bd-text shadow-bd-lg transition-opacity ${
        item.action ? "pointer-events-auto pe-2" : "pe-3.5"
      }`}
      style={{
        opacity: leaving ? 0 : 1,
        transitionDuration: `${FADE}ms`,
        animation: "bd-in 200ms ease-out",
      }}
    >
      <Icon
        size={18}
        weight="fill"
        className="flex-none"
        style={{ color: failure ? "var(--color-bd-danger)" : "var(--color-bd-accent)" }}
      />
      <span className={`min-w-0 flex-1 ${failure ? "text-bd-danger" : ""}`}>
        {failure ?? item.message}
      </span>
      {item.action ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (item.action) void act(item.action);
          }}
          className="h-8 flex-none cursor-pointer rounded-button border-0 bg-transparent px-2.5 text-[13px] font-semibold text-bd-accent hover:bg-bd-surface-2 disabled:cursor-default disabled:opacity-60"
        >
          {busy ? "…" : item.action.label}
        </button>
      ) : null}
    </div>
  );
}
