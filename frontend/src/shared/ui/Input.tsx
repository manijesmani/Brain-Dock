import type { InputHTMLAttributes, ReactNode } from "react";
import { forwardRef, useState } from "react";

/**
 * Rebuilt from the design reference.
 *
 * The mock imports this from an external design system that was not part of
 * the export, so the visual contract is taken from the surrounding fields:
 * 40px tall, 8px radius, the `--bd-bg` ground, a `--bd-border-2` edge, and on
 * focus the accent border with the soft accent ring the tokens define.
 */
interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  trailingIcon?: ReactNode;
  leadingIcon?: ReactNode;
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { trailingIcon, leadingIcon, invalid = false, className = "", ...props },
  ref,
) {
  const [focused, setFocused] = useState(false);

  const borderColor = invalid
    ? "var(--color-bd-danger)"
    : focused
      ? "var(--color-bd-accent)"
      : "var(--color-bd-border-2)";

  return (
    <div
      className="flex h-10 w-full items-center gap-2 rounded-input px-3 transition-colors"
      style={{
        background: "var(--color-bd-bg)",
        border: `1px solid ${borderColor}`,
        boxShadow: focused && !invalid ? "0 0 0 3px rgba(16,185,129,.18)" : "none",
      }}
    >
      {leadingIcon ? <span className="flex-none text-bd-text-3">{leadingIcon}</span> : null}
      <input
        ref={ref}
        {...props}
        onFocus={(event) => {
          setFocused(true);
          props.onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          props.onBlur?.(event);
        }}
        className={`min-w-0 flex-1 border-0 bg-transparent text-[13.5px] text-bd-text outline-none ${className}`}
      />
      {trailingIcon ? <span className="flex-none text-bd-text-3">{trailingIcon}</span> : null}
    </div>
  );
});
