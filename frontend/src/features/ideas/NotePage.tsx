import {
  ArchiveIcon,
  ArrowRightIcon,
  BellIcon,
  CheckIcon,
  CircleNotchIcon,
  HashIcon,
  ImageIcon,
  LightbulbIcon,
  PauseIcon,
  PlayIcon,
  TrashIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { EditorContent, useEditor } from "@tiptap/react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { EditorToolbar } from "@/features/ideas/editor/EditorToolbar";
import { editorExtensions } from "@/features/ideas/editor/extensions";
import { UNTITLED } from "@/features/ideas/untitled";
import { PremiumDialog } from "@/features/plans/PremiumNotice";
import { useApp } from "@/features/shell/appContext";
import { TrashIdeaDialog } from "@/features/trash/TrashIdeaDialog";
import {
  type IdeaWrite,
  useArchiveIdea,
  useIdea,
  useReminders,
  useSite,
  useUpdateIdea,
  useUploadAttachment,
} from "@/shared/api/queries";
import { errorMessage } from "@/shared/api/errors";
import { useToast } from "@/shared/hooks/useToast";
import { toPersianDigits } from "@/shared/lib/persian";
import { checkUpload, describeUpload } from "@/shared/lib/uploads";
import { Dropdown, type DropdownOption } from "@/shared/ui/Dropdown";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import { CategoryDot, PriorityDots } from "@/shared/ui/indicators";
import { PRIORITY_LABELS, STATUS_LABELS, statusColor } from "@/shared/ui/status";
import type { Attachment, Idea, IdeaPriority, IdeaStatus, TiptapDocument } from "@/types/domain";

/** How long the editor sits idle before the draft is sent. */
const AUTOSAVE_DELAY = 900;

type SaveState = "idle" | "saving" | "saved" | "failed";

const STATUS_OPTIONS: DropdownOption<IdeaStatus>[] = (
  ["idea", "planned", "doing", "done"] as const
).map((status) => ({ value: status, label: STATUS_LABELS[status] }));

const PRIORITY_OPTIONS: DropdownOption<IdeaPriority>[] = (["high", "mid", "low"] as const).map(
  (priority) => ({ value: priority, label: PRIORITY_LABELS[priority] }),
);

export function NotePage() {
  const { ideaId } = useParams();
  const id = Number(ideaId);
  const { data: idea, isPending, isError } = useIdea(Number.isNaN(id) ? null : id);

  // In the trash, deleted for good, never there, or another account's -- say
  // so, rather than leave an empty page that looks like it is still loading.
  if (isError || Number.isNaN(id)) return <MissingIdea />;

  if (isPending) {
    return <div className="min-h-page flex-1 bg-bd-bg" />;
  }

  // Keyed by the idea, so the editor and the title field are created once per
  // note. Copying the fetched values into state on every render instead would
  // overwrite whatever the user was typing on each background refetch.
  return <NoteEditor key={idea.id} idea={idea} />;
}

function NoteEditor({ idea }: { idea: Idea }) {
  const navigate = useNavigate();
  const { user, categories, openReminderDialog } = useApp();

  const { data: reminders = [] } = useReminders();
  const update = useUpdateIdea();
  const archive = useArchiveIdea();
  const upload = useUploadAttachment();
  const toast = useToast();
  const { data: site } = useSite();
  const location = useLocation();

  // What went wrong, said where it happened: under the header's buttons, or
  // beside the attachments for a file. Never a toast.
  const [problem, setProblem] = useState<{ where: "header" | "files"; text: string } | null>(null);
  const [trashing, setTrashing] = useState(false);

  // A request that failed used to leave the header's buttons doing nothing
  // at all -- no navigation, no word why -- which read as a button that does
  // not work. Now the reason is shown, in Persian.
  const attempt = async (run: () => Promise<unknown>, fallback: string) => {
    setProblem(null);
    try {
      await run();
      return true;
    } catch (caught) {
      setProblem({ where: "header", text: errorMessage(caught, fallback) });
      return false;
    }
  };

  // Opened straight from a link -- the Telegram bot's, a bookmark -- there
  // is no page in the app to go back to, and going back would leave it.
  const leave = () => (location.key === "default" ? navigate(ROUTES.ideas) : navigate(-1));

  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [premiumOpen, setPremiumOpen] = useState(false);
  // An untitled idea opens with an empty field to write the title into.
  const [title, setTitle] = useState(idea.title === UNTITLED ? "" : idea.title);
  const saveTimer = useRef<number | null>(null);
  const titleField = useRef<HTMLTextAreaElement>(null);
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
      flush().catch(() => setSaveState("failed"));
    }, AUTOSAVE_DELAY);
  };

  const flush = async () => {
    await update.mutateAsync({
      id: idea.id,
      title: title.trim() || UNTITLED,
      content: editor.getJSON() as TiptapDocument,
    });
    setSaveState("saved");
  };

  // A long title wraps rather than running out of sight, most of all on a
  // phone, so the field's height follows its text: on every edit (below) and
  // whenever the width changes the wrapping.
  useLayoutEffect(() => {
    const fit = () => fitToContent(titleField.current);
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  // Anything still pending when the page closes would otherwise be lost.
  useEffect(
    () => () => {
      if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    },
    [],
  );

  // A file is checked here first, so a wrong or oversized one is refused at
  // once rather than after it has travelled; the server checks again.
  const sendFile = (kind: "image" | "audio", file: File) => {
    const refusal = checkUpload(file, site?.uploads[kind], kind === "image" ? "عکس" : "فایل صوتی");
    if (refusal) {
      setProblem({ where: "files", text: refusal });
      return;
    }

    setProblem(null);
    setSaveState("saving");
    upload.mutate(
      { idea: idea.id, kind, file },
      {
        onSuccess: () => {
          setSaveState("saved");
          toast.show(kind === "image" ? "عکس اضافه شد" : "صدا اضافه شد");
        },
        onError: (caught) => {
          setSaveState("idle");
          setProblem({
            where: "files",
            text: errorMessage(caught, "افزودن فایل ناموفق بود. دوباره امتحان کن."),
          });
        },
      },
    );
  };

  // The editor's last changes go with the idea into the trash, so taking it
  // back out restores what was on screen.
  const saveBeforeLeaving = async () => {
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    if (saveState === "saving" || saveState === "failed") await flush();
  };

  const patch = (changes: IdeaWrite) => {
    setSaveState("saving");
    update.mutate(
      { ...changes, id: idea.id },
      { onSuccess: () => setSaveState("saved"), onError: () => setSaveState("failed") },
    );
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
    <div className="flex min-h-page min-w-0 flex-1 flex-col">
      <div className="sticky top-0 z-[1100] flex items-center gap-1 border-b border-bd-border bg-bd-bg px-3 py-[11px] sm:gap-2 sm:px-[26px]">
        <div className="flex-1" />

        <button
          type="button"
          onClick={() => {
            void (async () => {
              if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
              // Leaving waits for the last edits; if they cannot be saved,
              // stay rather than lose them.
              if (await attempt(flush, "ذخیرهٔ آخرین تغییرها ناموفق بود. دوباره امتحان کن.")) {
                void leave();
              } else {
                setSaveState("failed");
              }
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
              const done = await attempt(
                () => archive.mutateAsync({ id: idea.id }),
                "آرشیو کردن ناموفق بود. دوباره امتحان کن.",
              );
              if (done) {
                toast.show("ایده آرشیو شد");
                void navigate(ROUTES.archive);
              }
            })();
          }}
          className="inline-flex h-[34px] cursor-pointer items-center gap-[7px] rounded-button border-0 bg-transparent px-3 text-[13px] text-bd-text-2 hover:bg-bd-surface-2 hover:text-bd-text"
        >
          <ArchiveIcon size={16} />
          <span className="hidden sm:inline">آرشیو</span>
        </button>

        <button
          type="button"
          title="حذف"
          aria-label="حذف ایده"
          onClick={() => {
            setProblem(null);
            setTrashing(true);
          }}
          className="inline-flex h-[34px] cursor-pointer items-center gap-[7px] rounded-button border-0 bg-transparent px-3 text-[13px] text-bd-danger hover:bg-bd-surface-2"
        >
          <TrashIcon size={16} />
          <span className="hidden sm:inline">حذف</span>
        </button>
      </div>

      {problem?.where === "header" ? (
        <div className="sticky top-[57px] z-[1090] bg-bd-bg px-3 pt-2.5 sm:px-[26px]">
          <InlineAlert onDismiss={() => setProblem(null)}>{problem.text}</InlineAlert>
        </div>
      ) : null}

      <div className="flex-1 pt-8 pb-[150px] lg:pt-16">
        <div className="mx-auto max-w-[680px] px-4 sm:px-6">
          <textarea
            ref={titleField}
            rows={1}
            autoFocus={idea.title === UNTITLED}
            value={title}
            onChange={(event) => {
              // One line of text, however it is typed or pasted.
              setTitle(event.target.value.replace(/\n/g, " "));
              fitToContent(event.target);
              scheduleSave();
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.preventDefault();
            }}
            placeholder="عنوان"
            className="m-0 mb-[18px] block w-full resize-none pointer-coarse:min-h-11 overflow-hidden border-0 bg-transparent p-0 py-0.5 text-[22.5px] leading-[1.45] font-bold tracking-tight text-bd-text outline-none sm:text-[29px] lg:text-[34px]"
          />

          <div className="mb-6 flex flex-wrap items-center gap-2 border-b border-bd-border pb-5 sm:mb-[30px] sm:pb-[22px]">
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
              className="inline-flex h-[30px] cursor-pointer items-center gap-2 rounded-full border border-bd-border bg-transparent px-3 text-[11.5px] pointer-coarse:h-9 sm:gap-[7px] sm:px-[11px] sm:text-[12.5px] hover:bg-bd-surface-2"
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
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {images.map((image, index) => (
                  <ImageTile key={image.id} attachment={image} index={index} />
                ))}
              </div>
            </div>
          ) : null}

          {audio ? <AudioPlayer attachment={audio} /> : null}

          {user.can_attach_media && site ? (
            <p className="mt-8 mb-0 text-[12px] leading-[1.9] text-bd-text-3">
              عکس: {describeUpload(site.uploads.image)} · صدا: {describeUpload(site.uploads.audio)}
            </p>
          ) : null}

          {problem?.where === "files" ? (
            <InlineAlert
              className="mt-3 scroll-mb-[90px]"
              onDismiss={() => setProblem(null)}
              revealOnShow
            >
              {problem.text}
            </InlineAlert>
          ) : null}

          <input
            ref={imageInput}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) sendFile("image", file);
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
              if (file) sendFile("audio", file);
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
        mediaLocked={!user.can_attach_media}
        onLockedMedia={() => setPremiumOpen(true)}
      />
      <PremiumDialog open={premiumOpen} reason="media" onClose={() => setPremiumOpen(false)} />
      <TrashIdeaDialog
        idea={trashing ? { id: idea.id, title: title.trim() || UNTITLED } : null}
        onClose={() => setTrashing(false)}
        beforeTrash={saveBeforeLeaving}
        onTrashed={() => void leave()}
      />
    </div>
  );
}

/** Sets a textarea's height to that of its text. */
function fitToContent(element: HTMLTextAreaElement | null) {
  if (!element) return;
  element.style.height = "auto";
  element.style.height = `${element.scrollHeight}px`;
}

function SaveIndicator({ state }: { state: SaveState }) {
  if (state === "idle") return <span className="px-1.5" />;

  if (state === "failed") {
    // Shown on a phone too: an icon alone would not say what went wrong.
    return (
      <span className="inline-flex items-center gap-1.5 px-1.5 text-[12.5px] text-bd-danger">
        <WarningCircleIcon size={15} />
        ذخیره نشد
      </span>
    );
  }

  const saving = state === "saving";

  return (
    <span
      className="inline-flex items-center gap-1.5 px-1.5 text-[12.5px]"
      style={{
        color: saving ? "var(--color-bd-text-3)" : "var(--color-bd-accent)",
      }}
    >
      {saving ? <CircleNotchIcon size={15} className="animate-spin" /> : <CheckIcon size={15} />}
      <span className="hidden sm:inline">{saving ? "در حال ذخیره" : "ذخیره شد"}</span>
    </span>
  );
}

/** The note page for an idea that is not there, or not this account's. */
function MissingIdea() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-page flex-1 flex-col items-center justify-center gap-3 bg-bd-bg p-6 text-center">
      <LightbulbIcon size={28} className="text-bd-text-3" />
      <div className="text-[15px] font-semibold">این ایده پیدا نشد</div>
      <p className="m-0 max-w-[340px] text-[13px] leading-[1.8] text-bd-text-2">
        شاید حذف شده باشد، یا مال حساب دیگری باشد. اگر حساب دیگری داری، اول واردش شو.
      </p>
      <button
        type="button"
        onClick={() => void navigate(ROUTES.ideas)}
        className="mt-1 h-[38px] cursor-pointer rounded-button border-0 bg-bd-accent px-[15px] text-[13px] font-medium text-bd-accent-ink hover:bg-bd-accent-hover pointer-coarse:h-11"
      >
        رفتن به همهٔ ایده‌ها
      </button>
    </div>
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
        className="inline-flex h-[30px] max-w-full cursor-pointer items-center gap-2 rounded-full border border-bd-border bg-transparent px-3 text-[11.5px] pointer-coarse:h-9 sm:gap-[7px] sm:px-[11px] sm:text-[12.5px] text-bd-text-2 hover:bg-bd-surface-2"
      >
        <HashIcon size={14} className="flex-none" />
        <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">
          {selected.length > 0 ? selected.map((tag) => `#${tag}`).join(" ") : "بدون تگ"}
        </span>
      </button>

      {open ? (
        <>
          <div
            className="fixed inset-0 z-[1200] bg-black/40 sm:bg-transparent"
            onClick={() => setOpen(false)}
          />
          <div
            className="fixed inset-x-3 bottom-3 z-[1300] max-h-[65dvh] overflow-y-auto rounded-card border border-bd-border-2 bg-bd-surface-2 p-[5px] shadow-bd-lg sm:absolute sm:inset-x-auto sm:start-0 sm:top-9 sm:bottom-auto sm:max-h-none sm:min-w-[210px] sm:overflow-visible"
            style={{ animation: "bd-pop 150ms ease-out" }}
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
