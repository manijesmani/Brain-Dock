import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "@/shared/api/errors";
import { untrashIdea, useTrashIdea } from "@/shared/api/queries";
import { useToast } from "@/shared/hooks/useToast";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";

/**
 * «حذف» for an idea, wherever it is pressed: the list's row button and the
 * editor's. Asks first; then moves the idea to the trash and offers it back
 * from the toast for a few seconds.
 */
export function TrashIdeaDialog({
  idea,
  onClose,
  beforeTrash,
  onTrashed,
}: {
  /** The idea asked about; null while the dialog is closed. */
  idea: { id: number; title: string } | null;
  onClose: () => void;
  /** Runs first, and a failure stops the delete: the editor saves its last edits. */
  beforeTrash?: () => Promise<unknown>;
  /** Runs once the idea is in the trash: the editor leaves the page. */
  onTrashed?: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const trash = useTrashIdea();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    if (!idea) return;
    setError(null);
    setPending(true);

    try {
      await beforeTrash?.();
      await trash.mutateAsync(idea.id);
    } catch (caught) {
      setError(errorMessage(caught, "انتقال به سطل زباله ناموفق بود. دوباره امتحان کن."));
      setPending(false);
      return;
    }

    setPending(false);
    onClose();
    onTrashed?.();

    const { id } = idea;
    toast.show("ایده به سطل زباله منتقل شد", {
      action: {
        label: "بازگردانی",
        failure: "بازگردانی ناموفق بود. از «سطل زباله» دوباره امتحان کن.",
        run: async () => {
          await untrashIdea(client, id);
          toast.show("ایده بازگردانده شد");
        },
      },
    });
  };

  return (
    <ConfirmDialog
      open={idea !== null}
      title="آیا از حذف این ایده مطمئن هستید؟"
      confirmLabel="حذف"
      danger
      pending={pending}
      error={error}
      onConfirm={() => void confirm()}
      onClose={() => {
        setError(null);
        onClose();
      }}
    >
      <span className="line-clamp-3 font-semibold break-words text-bd-text">«{idea?.title}»</span>
      <span className="mt-1 block">
        به سطل زباله می‌رود و تا وقتی خودت پاکش نکنی، از آنجا برمی‌گردد.
      </span>
    </ConfirmDialog>
  );
}
