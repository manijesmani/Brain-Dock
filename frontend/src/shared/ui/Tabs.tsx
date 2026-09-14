export interface TabOption<T> {
  value: T;
  label: string;
}

interface TabsProps<T> {
  value: T;
  options: TabOption<T>[];
  onChange: (value: T) => void;
}

/** Text tabs with an accent underline, as the idea list's status filter. */
export function Tabs<T extends string>({ value, options, onChange }: TabsProps<T>) {
  return (
    <div role="tablist" className="flex items-center gap-[27.5px]">
      {options.map((option) => {
        const selected = option.value === value;

        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(option.value)}
            className={`relative h-10 cursor-pointer border-0 bg-transparent px-0.5 text-[17px] transition-colors hover:text-bd-text ${
              selected ? "font-semibold text-bd-text" : "text-bd-text-3"
            }`}
          >
            {option.label}
            {selected ? (
              <span className="absolute inset-x-0 bottom-[4px] h-0.5 rounded-full bg-bd-accent" />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
