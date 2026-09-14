import { useState } from "react";

import { useDeleteCategory, useSaveCategory } from "@/shared/api/queries";
import { Dialog } from "@/shared/ui/Dialog";
import { CATEGORY_COLORS, type Category } from "@/types/domain";

interface CategoryDialogProps {
  open: boolean;
  category: Category | null;
  onClose: () => void;
}

export function CategoryDialog({ open, category, onClose }: CategoryDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} width={500}>
      {/* Keyed so each opening starts from the record being edited rather
          than from whatever the previous opening left behind. */}
      <CategoryForm key={category?.id ?? "new"} category={category} onClose={onClose} />
    </Dialog>
  );
}

function CategoryForm({ category, onClose }: { category: Category | null; onClose: () => void }) {
  const [name, setName] = useState(category?.name ?? "");
  const [color, setColor] = useState<string>(category?.color ?? CATEGORY_COLORS[0]);
  const [error, setError] = useState<string | null>(null);

  const save = useSaveCategory();
  const remove = useDeleteCategory();

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("نام دسته نمی‌تواند خالی باشد.");
      return;
    }

    try {
      await save.mutateAsync({ id: category?.id, name: trimmed, color });
      onClose();
    } catch {
      setError("دسته‌ای با این نام از قبل وجود دارد.");
    }
  };

  return (
    <div className="p-5">
      <div className="mb-[19px] text-[17.5px] font-semibold">
        {category ? "ویرایش دسته" : "دستهٔ جدید"}
      </div>

      <label className="mb-[9px] block text-[15.5px] text-bd-text-2">نام دسته</label>
      <input
        autoFocus
        value={name}
        onChange={(event) => {
          setName(event.target.value);
          setError(null);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") void submit();
        }}
        placeholder="مثلاً محتوای یوتیوب"
        className="h-10 w-full rounded-button border bg-bd-bg px-3 text-[17px] text-bd-text outline-none"
        style={{
          borderColor: error ? "var(--color-bd-danger)" : "var(--color-bd-border-2)",
        }}
      />
      {error ? <div className="mt-2 text-[15px] text-bd-danger">{error}</div> : null}

      <label className="mt-4 mb-[11px] block text-[15.5px] text-bd-text-2">رنگ</label>
      <div className="flex flex-wrap gap-[11px]">
        {CATEGORY_COLORS.map((swatch) => (
          <button
            key={swatch}
            type="button"
            onClick={() => setColor(swatch)}
            aria-label={`رنگ ${swatch}`}
            className="size-[32.5px] cursor-pointer rounded-full border-0"
            style={{
              background: swatch,
              boxShadow: `0 0 0 2.5px var(--color-bd-surface), 0 0 0 5px ${
                swatch === color ? swatch : "transparent"
              }`,
            }}
          />
        ))}
      </div>

      <div className="mt-[27.5px] flex gap-[11px]">
        {category ? (
          <button
            type="button"
            onClick={() => {
              void (async () => {
                await remove.mutateAsync(category.id);
                onClose();
              })();
            }}
            className="h-[47.5px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[17.5px] text-[16px] text-bd-danger hover:bg-bd-surface-2"
          >
            حذف
          </button>
        ) : null}
        <div className="flex-1" />
        <button
          type="button"
          onClick={onClose}
          className="h-[47.5px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-[19px] text-[16px] text-bd-text hover:bg-bd-surface-2"
        >
          انصراف
        </button>
        <button
          type="button"
          onClick={() => void submit()}
          disabled={save.isPending}
          className="h-[47.5px] cursor-pointer rounded-button border-0 bg-bd-accent px-[22.5px] text-[16px] font-semibold text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
        >
          ذخیره
        </button>
      </div>
    </div>
  );
}
