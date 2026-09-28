import { CaretDownIcon, CheckIcon } from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

export interface DropdownOption<T> {
  value: T;
  label: string;
  /** Rendered before the label, e.g. a category's colour dot. */
  adornment?: ReactNode;
}

interface DropdownProps<T> {
  value: T;
  options: DropdownOption<T>[];
  onChange: (value: T) => void;
  /** Shown instead of the selected option's label, for the sort control. */
  label?: string;
  icon?: ReactNode;
  /** The pill shape used on the note page, rather than the toolbar's square. */
  variant?: "toolbar" | "pill";
  minWidth?: number;
  adornment?: ReactNode;
}

/**
 * The menu used by every filter, the sort control and the note page's chips.
 *
 * Closing is handled by a full-screen click catcher, exactly as the design
 * does it -- one element below the menu that swallows the next click anywhere.
 */
export function Dropdown<T extends string | number | null>({
  value,
  options,
  onChange,
  label,
  icon,
  variant = "toolbar",
  minWidth = 170,
  adornment,
}: DropdownProps<T>) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open]);

  const selected = options.find((option) => option.value === value);
  const text = label ?? selected?.label ?? "";

  const trigger =
    variant === "pill"
      ? "inline-flex h-[30px] items-center gap-2 rounded-full pointer-coarse:h-9 border border-bd-border bg-transparent px-3 text-[11.5px] text-bd-text hover:bg-bd-surface-2 sm:gap-[7px] sm:px-[11px] sm:text-[12.5px]"
      : "inline-flex h-10 items-center gap-[7px] rounded-button border border-bd-border-2 bg-bd-surface px-[13px] text-[13px] text-bd-text hover:bg-bd-surface-2";

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((current) => !current);
        }}
        className={`${trigger} cursor-pointer`}
      >
        {icon}
        {adornment ?? selected?.adornment}
        {text}
        {icon ? null : <CaretDownIcon size={13} className="text-bd-text-3" />}
      </button>

      {/* A popover under the trigger, except on a phone: there a trigger near
          the edge would push it off the screen, so it opens as a sheet along
          the bottom instead, over a dimmed page. */}
      {open ? (
        <>
          <div
            className="fixed inset-0 z-[1200] bg-black/40 sm:bg-transparent"
            onClick={() => setOpen(false)}
          />
          <div
            className={`fixed inset-x-3 bottom-3 z-[1300] max-h-[65dvh] overflow-y-auto rounded-card border border-bd-border-2 bg-bd-surface-2 p-[5px] shadow-bd-lg sm:absolute sm:inset-x-auto sm:start-0 sm:bottom-auto sm:max-h-none sm:overflow-visible ${
              variant === "pill" ? "sm:top-[36px]" : "sm:top-[46px]"
            }`}
            style={{ minWidth, animation: "bd-pop 150ms ease-out" }}
          >
            {options.map((option) => (
              <button
                key={String(option.value)}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className="flex h-10 w-full cursor-pointer items-center gap-2 rounded-[7px] border-0 bg-transparent px-[9px] text-right text-[13px] text-bd-text hover:bg-bd-surface-3 sm:h-8"
              >
                {option.adornment}
                <span className="flex-1 text-right">{option.label}</span>
                {option.value === value ? <CheckIcon size={14} className="text-bd-accent" /> : null}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
