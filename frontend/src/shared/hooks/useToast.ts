import { createContext, useContext } from "react";

/** A button on a toast, such as «بازگردانی» after a delete. */
export interface ToastAction {
  label: string;
  /** Runs when pressed. If it throws, the toast stays and says why. */
  run: () => Promise<unknown>;
  /** What the toast says when `run` fails without a message of its own. */
  failure?: string;
}

export interface ToastOptions {
  /** How long it stays: 3 seconds, or 5 with an action to press. */
  duration?: number;
  action?: ToastAction;
  /** A toast with the same key replaces the one on screen instead of stacking. */
  key?: string;
}

/**
 * Toasts confirm what went right. What went wrong is said in place, next to
 * the form or the button it concerns, never in a toast.
 */
export interface ToastApi {
  /** Shows a short message at the foot of the screen, gone again by itself. */
  show: (message: string, options?: ToastOptions) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);

/** The toasts of the nearest ToastProvider; see shared/ui/Toast. */
export function useToast(): ToastApi {
  const value = useContext(ToastContext);
  if (value === null) {
    throw new Error("useToast must be used inside a ToastProvider.");
  }
  return value;
}
