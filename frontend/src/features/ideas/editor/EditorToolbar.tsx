import {
  CheckSquareIcon,
  CodeIcon,
  HighlighterIcon,
  ImageIcon,
  ListBulletsIcon,
  ListNumbersIcon,
  MicrophoneIcon,
  MinusIcon,
  QuotesIcon,
  TextBIcon,
  TextHOneIcon,
  TextHThreeIcon,
  TextHTwoIcon,
  TextItalicIcon,
  TextStrikethroughIcon,
  TextUnderlineIcon,
  UploadSimpleIcon,
} from "@phosphor-icons/react";
import type { Editor } from "@tiptap/react";
import type { ReactNode } from "react";

import { Crown } from "@/features/plans/PremiumNotice";

/**
 * The bottom-anchored toolbar, in the design's order and grouping.
 *
 * The mock drives these with `document.execCommand`, which is deprecated and
 * behaves differently in every browser. The commands are Tiptap's instead;
 * the layout, icons and titles are unchanged.
 */
interface EditorToolbarProps {
  editor: Editor | null;
  onPickImage: () => void;
  onPickAudio: () => void;
  onRecordAudio: () => void;
  /**
   * Pictures and audio need a special account. Without one the three tools
   * stay in place, marked with a crown, and explain themselves instead.
   */
  mediaLocked?: boolean;
  onLockedMedia?: () => void;
}

export function EditorToolbar({
  editor,
  onPickImage,
  onPickAudio,
  onRecordAudio,
  mediaLocked = false,
  onLockedMedia,
}: EditorToolbarProps) {
  if (!editor) return null;

  const chain = () => editor.chain().focus();
  const media = (run: () => void) => (mediaLocked ? () => onLockedMedia?.() : run);

  return (
    <div
      // Too many tools for a phone's width, so there the strip scrolls sideways.
      className="bd-no-scrollbar fixed bottom-0 z-[1140] flex items-center gap-1.5 overflow-x-auto pointer-coarse:gap-2.5 border-t border-bd-border bg-bd-surface px-2 py-[9px] sm:px-[26px]"
      style={{ insetInline: 0 }}
    >
      <Tool title="ضخیم" active={editor.isActive("bold")} onRun={() => chain().toggleBold().run()}>
        <TextBIcon size={17} />
      </Tool>
      <Tool
        title="مورب"
        active={editor.isActive("italic")}
        onRun={() => chain().toggleItalic().run()}
      >
        <TextItalicIcon size={17} />
      </Tool>
      <Tool
        title="زیرخط"
        active={editor.isActive("underline")}
        onRun={() => chain().toggleUnderline().run()}
      >
        <TextUnderlineIcon size={17} />
      </Tool>
      <Tool
        title="خط‌خورده"
        active={editor.isActive("strike")}
        onRun={() => chain().toggleStrike().run()}
      >
        <TextStrikethroughIcon size={17} />
      </Tool>
      <Tool
        title="هایلایت"
        active={editor.isActive("highlight")}
        onRun={() => chain().toggleHighlight().run()}
      >
        <HighlighterIcon size={17} />
      </Tool>

      <Divider />

      <Tool
        title="عنوان بزرگ"
        active={editor.isActive("heading", { level: 1 })}
        onRun={() => chain().toggleHeading({ level: 1 }).run()}
      >
        <TextHOneIcon size={17} />
      </Tool>
      <Tool
        title="عنوان متوسط"
        active={editor.isActive("heading", { level: 2 })}
        onRun={() => chain().toggleHeading({ level: 2 }).run()}
      >
        <TextHTwoIcon size={17} />
      </Tool>
      <Tool
        title="عنوان کوچک"
        active={editor.isActive("heading", { level: 3 })}
        onRun={() => chain().toggleHeading({ level: 3 }).run()}
      >
        <TextHThreeIcon size={17} />
      </Tool>

      <Divider />

      <Tool
        title="لیست نقطه‌ای"
        active={editor.isActive("bulletList")}
        onRun={() => chain().toggleBulletList().run()}
      >
        <ListBulletsIcon size={17} />
      </Tool>
      <Tool
        title="لیست شماره‌دار"
        active={editor.isActive("orderedList")}
        onRun={() => chain().toggleOrderedList().run()}
      >
        <ListNumbersIcon size={17} />
      </Tool>
      <Tool
        title="چک‌لیست"
        active={editor.isActive("taskList")}
        onRun={() => chain().toggleTaskList().run()}
      >
        <CheckSquareIcon size={17} />
      </Tool>

      <Divider />

      <Tool
        title="نقل‌قول"
        active={editor.isActive("blockquote")}
        onRun={() => chain().toggleBlockquote().run()}
      >
        <QuotesIcon size={17} />
      </Tool>
      <Tool
        title="کد"
        active={editor.isActive("codeBlock")}
        onRun={() => chain().toggleCodeBlock().run()}
      >
        <CodeIcon size={17} />
      </Tool>
      <Tool title="جداکننده" onRun={() => chain().setHorizontalRule().run()}>
        <MinusIcon size={17} />
      </Tool>

      <Divider />

      <Tool title="افزودن عکس" locked={mediaLocked} onRun={media(onPickImage)}>
        <ImageIcon size={17} />
      </Tool>
      <Tool title="ضبط صدا" locked={mediaLocked} onRun={media(onRecordAudio)}>
        <MicrophoneIcon size={17} />
      </Tool>
      <Tool title="آپلود صدا" locked={mediaLocked} onRun={media(onPickAudio)}>
        <UploadSimpleIcon size={17} />
      </Tool>

      <div className="flex-1" />
    </div>
  );
}

function Tool({
  title,
  active = false,
  locked = false,
  onRun,
  children,
}: {
  title: string;
  active?: boolean;
  /** Needs a special account: dimmed, with a crown in the corner. */
  locked?: boolean;
  onRun: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={locked ? `${title} · مخصوص کاربر ویژه` : title}
      // Mouse-down rather than click, so the editor never loses its selection
      // before the command runs.
      onMouseDown={(event) => {
        event.preventDefault();
        onRun();
      }}
      className="relative grid size-[34px] flex-none cursor-pointer place-items-center rounded-button border-0 hover:bg-bd-surface-3 hover:text-bd-text"
      style={{
        background: active ? "var(--color-bd-surface-3)" : "transparent",
        color: active
          ? "var(--color-bd-accent)"
          : locked
            ? "var(--color-bd-text-3)"
            : "var(--color-bd-text-2)",
      }}
    >
      {children}
      {locked ? <Crown size={11} className="absolute end-[3px] top-[3px]" /> : null}
    </button>
  );
}

function Divider() {
  return <span className="mx-[5px] h-[22px] w-px flex-none bg-bd-border" />;
}
