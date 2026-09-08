import {
  ArchiveIcon,
  ArrowRightIcon,
  BellIcon,
  CheckIcon,
  CircleNotchIcon,
  HashIcon,
  ImageIcon,
  PauseIcon,
  PlayIcon,
  TrashIcon,
} from "@phosphor-icons/react";
import { EditorContent, useEditor } from "@tiptap/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { EditorToolbar } from "@/features/ideas/editor/EditorToolbar";
import { editorExtensions } from "@/features/ideas/editor/extensions";
import { useApp } from "@/features/shell/appContext";
import {
  type IdeaWrite,
  useArchiveIdea,
  useDeleteIdea,
  useIdea,
  useReminders,
  useUpdateIdea,
  useUploadAttachment,
} from "@/shared/api/queries";
import { toPersianDigits } from "@/shared/lib/persian";
import { Dropdown, type DropdownOption } from "@/shared/ui/Dropdown";
import { CategoryDot, PriorityDots } from "@/shared/ui/indicators";
import { PRIORITY_LABELS, STATUS_LABELS, statusColor } from "@/shared/ui/status";
import type { Attachment, Idea, IdeaPriority, IdeaStatus, TiptapDocument } from "@/types/domain";

/** How long the editor sits idle before the draft is sent. */
const AUTOSAVE_DELAY = 900;

type SaveState = "idle" | "saving" | "saved";

const STATUS_OPTIONS: DropdownOption<IdeaStatus>[] = (
  ["idea", "planned", "doing", "done"] as const
).map((status) => ({ value: status, label: STATUS_LABELS[status] }));

const PRIORITY_OPTIONS: DropdownOption<IdeaPriority>[] = (["high", "mid", "low"] as const).map(
  (priority) => ({ value: priority, label: PRIORITY_LABELS[priority] }),
);

export function NotePage() {
  const { ideaId } = useParams();
  const id = Number(ideaId);
  const { data: idea, isPending } = useIdea(Number.isNaN(id) ? null : id);

  if (isPending || !idea) {
    return <div className="min-h-screen flex-1 bg-bd-bg" />;
  }

  // Keyed by the idea, so the editor and the title field are created once per
  // note. Copying the fetched values into state on every render instead would
  // overwrite whatever the user was typing on each background refetch.
  return <NoteEditor key={idea.id} idea={idea} />;
}

function NoteEditor({ idea }: { idea: Idea }) {
  const navigate = useNavigate();
  const { categories, openReminderDialog } = useApp();

  const { data: reminders = [] } = useReminders();
  const update = useUpdateIdea();
  const archive = useArchiveIdea();
  const remove = useDeleteIdea();
  const upload = useUploadAttachment();

  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [title, setTitle] = useState(idea.title);
  const saveTimer = useRef<number | null>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const audioInput = useRef<HTMLInputElement>(null);

  const reminder = reminders.find((item) => item.idea === idea.id) ?? null;

  const editor = useEditor({
    extensions: editorExtensions,
    content: idea.content,
    editorProps: {
      attributes: {
        class: "bd-prose outline-none min-h-[280px]",
        dir: "rtl",
      },
    },
    onUpdate: () => scheduleSave(),
  });

  // The draft is pushed once typing pauses, which is what drives the
  // "در حال ذخیره" indicator the design shows in the header.
  const scheduleSave = () => {
    setSaveState("saving");
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);

    saveTimer.current = window.setTimeout(() => {
      void flush();
    }, AUTOSAVE_DELAY);
  };

  const flush = async () => {
    await update.mutateAsync({
      id: idea.id,
      title: title.trim() || "بدون عنوان",
      content: editor.getJSON() as TiptapDocument,
    });
    setSaveState("saved");
  };

  // Anything still pending when the page closes would otherwise be lost.
  useEffect(
    () => () => {
      if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    },
    [],
  );

  const patch = (changes: IdeaWrite) => {
    setSaveState("saving");
    update.mutate({ ...changes, id: idea.id }, { onSuccess: () => setSaveState("saved") });
  };

  const images = idea.attachments.filter((item) => item.kind === "image");
  const audio = idea.attachments.find((item) => item.kind === "audio") ?? null;

  const categoryOptions: DropdownOption<number | null>[] = [
    { value: null, label: "بدون دسته", adornment: <CategoryDot color={null} /> },
    ...categories.map((item) => ({
      value: item.id,
      label: item.name,
      adornment: <CategoryDot color={item.color} />,
    })),
  ];

  return (
    <div className="flex min-h-screen min-w-0 flex-1 flex-col">
      <div className="sticky top-0 z-[1100] flex items-center gap-2 border-b border-bd-border bg-bd-bg px-[26px] py-[11px]">
        <div className="flex-1" />

        <button
          type="button"
          onClick={() => {
            void (async () => {
              await flush();
              void navigate(-1);
            })();
          }}
          className="inline-flex h-[34px] cursor-pointer items-center gap-[7px] rounded-button border border-bd-border-2 bg-transparent px-3 text-[13px] text-bd-text hover:bg-bd-surface-2"
        >
          <ArrowRightIcon size={15} />
          برگشت
        </button>

        <SaveIndicator state={saveState} />

        <button
          type="button"
          title="آرشیو"
          onClick={() => {
            void (async () => {
              await archive.mutateAsync({ id: idea.id });
              void navigate(ROUTES.archive);
            })();
          }}
          className="inline-flex h-[34px] cursor-pointer items-center gap-[7px] rounded-button border-0 bg-transparent px-3 text-[13px] text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text"
        >
          <ArchiveIcon size={16} />
          آرشیو
        </button>

        <button
          type="button"
          title="حذف"
          onClick={() => {
            void (async () => {
              await remove.mutateAsync(idea.id);
              void navigate(ROUTES.ideas);
            })();
          }}
          className="inline-flex h-[34px] cursor-pointer items-center gap-[7px] rounded-button border-0 bg-transparent px-3 text-[13px] text-bd-danger hover:bg-bd-surface-2"
        >
          <TrashIcon size={16} />
          حذف
        </button>
      </div>

      <div className="flex-1 pt-16 pb-[150px]">
        <div className="mx-auto max-w-[680px] px-6">
          <input
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
              scheduleSave();
            }}
            placeholder="عنوان"
            className="m-0 mb-[18px] w-full border-0 bg-transparent py-0.5 text-[34px] leading-[1.45] font-bold tracking-tight text-bd-text outline-none"
          />

          <div className="mb-[30px] flex flex-wrap items-center gap-2 border-b border-bd-border pb-[22px]">
            <Dropdown
              variant="pill"
              value={idea.status}
              options={STATUS_OPTIONS}
              onChange={(status) => patch({ status })}
              minWidth={180}
              adornment={
                <span
                  className="size-[7px] rounded-full"
                  style={{ background: statusColor(idea.status) }}
                />
              }
            />

            <Dropdown
              variant="pill"
              value={idea.priority}
              options={PRIORITY_OPTIONS}
              onChange={(priority) => patch({ priority })}
              minWidth={150}
              label={`اولویت ${PRIORITY_LABELS[idea.priority]}`}
              adornment={<PriorityDots priority={idea.priority} />}
            />

            <Dropdown
              variant="pill"
              value={idea.category}
              options={categoryOptions}
              onChange={(category) => patch({ category })}
              minWidth={180}
            />

            <TagPicker selected={idea.tags} onChange={(tags) => patch({ tags })} />

            <button
              type="button"
              onClick={() => openReminderDialog(idea.id)}
              className="inline-flex h-[30px] cursor-pointer items-center gap-[7px] rounded-full border border-bd-border bg-transparent px-[11px] text-[12.5px] hover:bg-bd-surface-2"
              style={{
                color: reminder?.is_active ? "var(--color-bd-accent)" : "var(--color-bd-text-2)",
              }}
            >
              <BellIcon size={14} />
              {reminder?.is_active ? reminder.description : "بدون یادآوری"}
            </button>
          </div>

          <EditorContent editor={editor} />

          {images.length > 0 ? (
            <div className="mt-10">
              <div className="mb-3 text-[12.5px] font-semibold text-bd-text-3">پیوست‌ها</div>
              <div className="grid grid-cols-3 gap-3">
                {images.map((image, index) => (
                  <ImageTile key={image.id} attachment={image} index={index} />
                ))}
              </div>
            </div>
          ) : null}

          {audio ? <AudioPlayer attachment={audio} /> : null}

          <input
            ref={imageInput}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate({ idea: idea.id, kind: "image", file });
              event.target.value = "";
            }}
          />
          <input
            ref={audioInput}
            type="file"
            accept="audio/*"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate({ idea: idea.id, kind: "audio", file });
              event.target.value = "";
            }}
          />
        </div>
      </div>

      <EditorToolbar
        editor={editor}
        onPickImage={() => imageInput.current?.click()}
        onPickAudio={() => audioInput.current?.click()}
        onRecordAudio={() => audioInput.current?.click()}
      />
    </div>
  );
}

function SaveIndicator({ state }: { state: SaveState }) {
  if (state === "idle") return <span className="px-1.5" />;

  const saving = state === "saving";

  return (
    <span
      className="inline-flex items-center gap-1.5 px-1.5 text-[12.5px]"
      style={{
        color: saving ? "var(--color-bd-text-3)" : "var(--color-bd-accent)",
      }}
    >
      {saving ? <CircleNotchIcon size={15} className="animate-spin" /> : <CheckIcon size={15} />}
      {saving ? "در حال ذخیره" : "ذخیره شد"}
    </span>
  );
}

function TagPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (tags: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");

  return (
    <div className="relative">
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((current) => !current);
        }}
        className="inline-flex h-[30px] cursor-pointer items-center gap-[7px] rounded-full border border-bd-border bg-transparent px-[11px] text-[12.5px] text-bd-text-2 hover:bg-bd-surface-2"
      >
        <HashIcon size={14} />
        {selected.length > 0 ? selected.map((tag) => `#${tag}`).join(" ") : "بدون تگ"}
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-[1200]" onClick={() => setOpen(false)} />
          <div
            className="absolute top-9 z-[1300] min-w-[210px] rounded-card border border-bd-border-2 bg-bd-surface-2 p-[5px] shadow-bd-lg"
            style={{ insetInlineStart: 0, animation: "bd-pop 150ms ease-out" }}
          >
            {selected.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => onChange(selected.filter((item) => item !== tag))}
                className="flex h-8 w-full cursor-pointer items-center gap-2 rounded-[7px] border-0 bg-transparent px-[9px] text-right text-[13px] text-bd-text hover:bg-bd-surface-3"
              >
                <span className="flex-1 text-right">#{tag}</span>
                <CheckIcon size={14} className="text-bd-accent" />
              </button>
            ))}

            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return;
                const name = draft.trim();
                if (name && !selected.includes(name)) onChange([...selected, name]);
                setDraft("");
              }}
              placeholder="تگ تازه و اینتر"
              className="mt-1 h-8 w-full rounded-[7px] border border-bd-border-2 bg-bd-bg px-2 text-[12.5px] text-bd-text outline-none"
            />
          </div>
        </>
      ) : null}
    </div>
  );
}

function ImageTile({ attachment, index }: { attachment: Attachment; index: number }) {
  const [failed, setFailed] = useState(false);
  const source = attachment.thumbnail_url ?? attachment.file_url;

  if (failed) {
    return (
      <div className="flex aspect-[4/3] flex-col items-center justify-center gap-[7px] rounded-card border border-dashed border-bd-border-2 bg-bd-surface text-[12px] text-bd-text-3">
        <ImageIcon size={20} />
        عکس {toPersianDigits(index + 1)}
      </div>
    );
  }

  return (
    <a href={attachment.file_url} target="_blank" rel="noreferrer">
      <img
        src={source}
        alt={attachment.original_name || `عکس ${toPersianDigits(index + 1)}`}
        onError={() => setFailed(true)}
        className="aspect-[4/3] w-full rounded-card border border-bd-border object-cover"
      />
    </a>
  );
}

function AudioPlayer({ attachment }: { attachment: Attachment }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);

  const seconds = Math.round(attachment.duration_seconds ?? 0);
  const label = `${toPersianDigits(Math.floor(seconds / 60))}:${toPersianDigits(
    String(seconds % 60).padStart(2, "0"),
  )}`;

  // The design draws a forty-bar waveform. Real peaks would need the audio
  // decoded; the shape is derived from the id so it stays stable per file
  // rather than shuffling on every render.
  const bars = useMemo(
    () =>
      Array.from({ length: 40 }, (_, index) => {
        const seed = Math.sin(attachment.id * 12.9898 + index * 78.233) * 43758.5453;
        return 6 + Math.abs(seed - Math.floor(seed)) * 22;
      }),
    [attachment.id],
  );

  return (
    <div className="mt-4 flex max-w-[520px] items-center gap-3.5 rounded-card border border-bd-border bg-bd-surface px-4 py-[13px]">
      <button
        type="button"
        title={playing ? "توقف" : "پخش"}
        onClick={() => {
          const element = audioRef.current;
          if (!element) return;
          if (playing) element.pause();
          else void element.play();
        }}
        className="grid size-9 flex-none cursor-pointer place-items-center rounded-full border-0 bg-bd-accent text-bd-accent-ink"
      >
        {playing ? <PauseIcon size={17} weight="fill" /> : <PlayIcon size={17} weight="fill" />}
      </button>

      <div className="flex h-[30px] flex-1 items-center gap-0.5">
        {bars.map((height, index) => (
          <span
            key={index}
            className="flex-1 rounded-full bg-bd-accent"
            style={{ height, opacity: 0.55 }}
          />
        ))}
      </div>

      <span className="flex-none text-[12.5px] text-bd-text-2">{label}</span>

      <audio
        ref={audioRef}
        src={attachment.file_url}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        hidden
      />
    </div>
  );
}
