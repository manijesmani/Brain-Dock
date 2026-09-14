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
  minWidth = 212.5,
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
      ? "inline-flex h-[37.5px] items-center gap-[9px] rounded-full border border-bd-border bg-transparent px-[14px] text-[15.5px] text-bd-text hover:bg-bd-surface-2"
      : "inline-flex h-10 items-center gap-[9px] rounded-button border border-bd-border-2 bg-bd-surface px-[16px] text-[16px] text-bd-text hover:bg-bd-surface-2";

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
        {icon ? null : <CaretDownIcon size={16} className="text-bd-text-3" />}
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-[1200]" onClick={() => setOpen(false)} />
          <div
            className="absolute z-[1300] rounded-card border border-bd-border-2 bg-bd-surface-2 p-[6px] shadow-bd-lg"
            style={{
              insetInlineStart: 0,
              top: variant === "pill" ? 45 : 57.5,
              minWidth,
              animation: "bd-pop 150ms ease-out",
            }}
          >
            {options.map((option) => (
              <button
                key={String(option.value)}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className="flex h-8 w-full cursor-pointer items-center gap-2 rounded-[9px] border-0 bg-transparent px-[11px] text-right text-[16px] text-bd-text hover:bg-bd-surface-3"
              >
                {option.adornment}
                <span className="flex-1 text-right">{option.label}</span>
                {option.value === value ? (
                  <CheckIcon size={17.5} className="text-bd-accent" />
                ) : null}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
