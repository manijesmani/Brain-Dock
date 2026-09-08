/**
 * Rebuilt from the design reference.
 *
 * Like the input, this came from an external design system the export did not
 * include. The size is fixed by the mock's own hint -- 40 by 22 -- and the
 * colours come from the accent tokens.
 */
interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
}

export function Switch({ checked, onChange, label, disabled = false }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="relative h-[22px] w-10 flex-none rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50"
      style={{
        background: checked ? "var(--color-bd-accent)" : "var(--color-bd-surface-3)",
        border: `1px solid ${checked ? "var(--color-bd-accent)" : "var(--color-bd-border-2)"}`,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      <span
        className="absolute top-1/2 block size-4 -translate-y-1/2 rounded-full transition-[inset-inline-start] duration-200 ease-out"
        style={{
          // Right-to-left: the knob sits at the start edge when off.
          insetInlineStart: checked ? "2px" : "18px",
          background: checked ? "var(--color-bd-accent-ink)" : "var(--color-bd-text-3)",
        }}
      />
    </button>
  );
}
