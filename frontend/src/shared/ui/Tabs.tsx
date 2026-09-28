export interface TabOption<T> {
  value: T;
  label: string;
}

interface TabsProps<T> {
  value: T;
  options: TabOption<T>[];
  onChange: (value: T) => void;
}

/**
 * Text tabs with an accent underline, as the idea list's status filter. On a
 * screen too narrow for all of them the strip scrolls sideways.
 */
export function Tabs<T extends string>({ value, options, onChange }: TabsProps<T>) {
  return (
    <div
      role="tablist"
      className="bd-no-scrollbar flex items-center gap-[16px] overflow-x-auto sm:gap-[22px] pointer-coarse:gap-5 pointer-coarse:px-2 pointer-coarse:sm:gap-[22px]"
    >
      {options.map((option) => {
        const selected = option.value === value;

        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(option.value)}
            className={`relative h-10 flex-none pointer-coarse:h-11 cursor-pointer border-0 bg-transparent px-0.5 text-[13.5px] whitespace-nowrap transition-colors hover:text-bd-text ${
              selected ? "font-semibold text-bd-text" : "text-bd-text-3"
            }`}
          >
            {option.label}
            {selected ? (
              <span className="absolute inset-x-0 bottom-[3px] h-0.5 rounded-full bg-bd-accent" />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
