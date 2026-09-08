import Highlight from "@tiptap/extension-highlight";
import Placeholder from "@tiptap/extension-placeholder";
import TaskItem from "@tiptap/extension-task-item";
import TaskList from "@tiptap/extension-task-list";
import Underline from "@tiptap/extension-underline";
import StarterKit from "@tiptap/starter-kit";

/**
 * The editor's capabilities, kept to exactly what the design's toolbar offers.
 *
 * This list has to stay in step with the allow-list in
 * `backend/apps/ideas/content.py`: anything enabled here that the server does
 * not recognise is stripped on save, and the user watches their formatting
 * disappear.
 */
export const editorExtensions = [
  StarterKit.configure({
    // Only the three levels the toolbar exposes.
    heading: { levels: [1, 2, 3] },
    // The design has no link button, and the server strips link marks.
    link: false,
  }),
  Underline,
  Highlight,
  TaskList,
  TaskItem.configure({ nested: false }),
  Placeholder.configure({ placeholder: "بنویس…" }),
];
