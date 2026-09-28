import { NotePencilIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { UNTITLED } from "@/features/ideas/untitled";
import { PremiumNotice } from "@/features/plans/PremiumNotice";
import { useApp } from "@/features/shell/appContext";
import { useCreateIdea } from "@/shared/api/queries";
import { errorMessage } from "@/shared/api/errors";
import { useToast } from "@/shared/hooks/useToast";
import { Dialog } from "@/shared/ui/Dialog";

interface QuickCaptureDialogProps {
  open: boolean;
  onClose: () => void;
  categoryId: number | null;
}

/** The whole point of the product: getting an idea down in one keystroke. */
export function QuickCaptureDialog({ open, onClose, categoryId }: QuickCaptureDialogProps) {
  const { user } = useApp();
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const toast = useToast();
  const createIdea = useCreateIdea();

  // A guest or a free account that already holds all it may is told so
  // here, instead of finding out from a refusal after typing.
  const full = user.idea_limit !== null && user.idea_count >= user.idea_limit;

  const close = () => {
    setTitle("");
    setError(null);
    onClose();
  };

  const submit = async (openEditor: boolean) => {
    const trimmed = title.trim();
    // Saving from here needs a title. Opening the full editor does not: the
    // title can be written there, so the idea starts as untitled.
    if ((!trimmed && !openEditor) || createIdea.isPending) return;

    setError(null);
    try {
      const idea = await createIdea.mutateAsync({
        title: trimmed || UNTITLED,
        category: categoryId,
      });
      close();

      // Either way, straight on to the idea just made.
      void navigate(ROUTES.note.replace(":ideaId", String(idea.id)));
      toast.show("ایده با موفقیت ثبت شد");
    } catch (caught) {
      setError(errorMessage(caught, "ثبت ایده ناموفق بود. دوباره امتحان کن."));
    }
  };

  return (
    <Dialog open={open} onClose={close} width={430}>
      {full ? (
        <PremiumNotice user={user} reason="ideas" onClose={close} />
      ) : (
        <div className="p-5">
          <div className="mb-[13px] text-[14px] font-semibold">ثبت سریع ایده</div>
          <div className="flex gap-[9px]">
            <input
              autoFocus
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void submit(false);
              }}
              placeholder="ایده‌ات چیست؟"
              className="h-[42px] min-w-0 flex-1 rounded-[9px] pointer-coarse:h-11 border border-bd-border-2 bg-bd-bg px-[13px] text-[14px] text-bd-text outline-none"
            />
            <button
              type="button"
              onClick={() => void submit(false)}
              disabled={createIdea.isPending}
              className="h-[42px] cursor-pointer rounded-[9px] border-0 bg-bd-accent pointer-coarse:h-11 px-5 text-[13.5px] font-semibold text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
            >
              ثبت
            </button>
          </div>
          {error ? (
            <div className="mt-2.5 text-[12.5px] leading-[1.8] text-bd-danger">{error}</div>
          ) : null}
          {/* A proper button rather than a text link: going straight to the
              full editor, title or not, is the common way in. */}
          <button
            type="button"
            onClick={() => void submit(true)}
            disabled={createIdea.isPending}
            className="mt-3 inline-flex h-[38px] w-full cursor-pointer items-center justify-center gap-2 rounded-[9px] border border-bd-border-2 bg-transparent text-[13px] text-bd-text hover:border-bd-accent hover:text-bd-accent disabled:opacity-60"
          >
            <NotePencilIcon size={16} />
            باز کردن ادیتور کامل
          </button>
        </div>
      )}
    </Dialog>
  );
}
