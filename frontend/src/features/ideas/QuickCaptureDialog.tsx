import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { useCreateIdea } from "@/shared/api/queries";
import { Dialog } from "@/shared/ui/Dialog";

interface QuickCaptureDialogProps {
  open: boolean;
  onClose: () => void;
  categoryId: number | null;
}

/** The whole point of the product: getting an idea down in one keystroke. */
export function QuickCaptureDialog({ open, onClose, categoryId }: QuickCaptureDialogProps) {
  const [title, setTitle] = useState("");
  const navigate = useNavigate();
  const createIdea = useCreateIdea();

  const close = () => {
    setTitle("");
    onClose();
  };

  const submit = async (openEditor: boolean) => {
    const trimmed = title.trim();
    if (!trimmed || createIdea.isPending) return;

    const idea = await createIdea.mutateAsync({ title: trimmed, category: categoryId });
    close();

    if (openEditor) void navigate(ROUTES.note.replace(":ideaId", String(idea.id)));
  };

  return (
    <Dialog open={open} onClose={close} width={537.5}>
      <div className="p-5">
        <div className="mb-[16px] text-[17.5px] font-semibold">ثبت سریع ایده</div>
        <div className="flex gap-[11px]">
          <input
            autoFocus
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void submit(false);
            }}
            placeholder="ایده‌ات چیست؟"
            className="h-[52.5px] flex-1 rounded-[11px] border border-bd-border-2 bg-bd-bg px-[16px] text-[17.5px] text-bd-text outline-none"
          />
          <button
            type="button"
            onClick={() => void submit(false)}
            disabled={createIdea.isPending}
            className="h-[52.5px] cursor-pointer rounded-[11px] border-0 bg-bd-accent px-5 text-[17px] font-semibold text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
          >
            ثبت
          </button>
        </div>
        <button
          type="button"
          onClick={() => void submit(true)}
          className="mt-3 cursor-pointer border-0 bg-transparent p-0 text-[15.5px] text-bd-text-3 underline underline-offset-[4px] hover:text-bd-accent"
        >
          باز کردن ادیتور کامل
        </button>
      </div>
    </Dialog>
  );
}
