/** Shapes returned by the API. Mirrors the serializers in the backend. */

export type IdeaStatus = "idea" | "planned" | "doing" | "done" | "archived";
export type IdeaPriority = "low" | "mid" | "high";
export type AttachmentKind = "image" | "audio";
export type RecurrenceKind = "daily" | "weekly" | "monthly" | "exact";
export type NotificationKind = "reminder" | "stale" | "telegram_capture";

/** The fixed eight-colour palette; a category may hold no other value. */
export const CATEGORY_COLORS = [
  "#3B82F6",
  "#8B5CF6",
  "#06B6D4",
  "#F472B6",
  "#F59E0B",
  "#94A3B8",
  "#EF4444",
  "#14B8A6",
] as const;

export type CategoryColor = (typeof CATEGORY_COLORS)[number];

/**
 * The kind of account, which is all that decides what it may do: guest,
 * regular ("free"), special ("premium") or the site's owner. The server
 * decides it; see apps.users.plans.
 */
export type Plan = "guest" | "free" | "premium" | "owner";

export interface CurrentUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  display_name: string;
  stale_after_days: number;
  is_telegram_linked: boolean;
  telegram_linked_at: string | null;
  /** Changes with every new picture, so it can be cached against. */
  avatar_url: string | null;
  plan: Plan;
  /** How many ideas the account may hold, archived ones included; null is no limit. */
  idea_limit: number | null;
  idea_count: number;
  can_attach_media: boolean;
  can_use_telegram: boolean;
  /** The owner's user panel. */
  can_manage_users: boolean;
}

/** A browser signed in to the account; see apps.users.devices. */
export interface Device {
  id: number;
  /** «Chrome روی Android», or «دستگاه نامشخص» for one signed in before the list existed. */
  name: string;
  kind: "mobile" | "tablet" | "desktop" | "unknown";
  user_agent: string;
  ip_address: string | null;
  signed_in_at: string | null;
  last_seen_at: string | null;
  /** The device this page is open on. */
  current: boolean;
}

/** An account as the owner's user panel lists it. */
export interface PanelUser {
  id: number;
  username: string;
  first_name: string;
  display_name: string;
  plan: Plan;
  idea_count: number;
  date_joined: string;
}

/** What one kind of upload may be; see core.views.SiteView. */
export interface UploadLimit {
  max_bytes: number;
  /** The accepted formats, already written out in Persian. */
  formats: string;
  /** MIME types to check before sending; absent where the server decides. */
  types?: string[];
}

/** What the site tells visitors before any session exists. */
export interface SiteInfo {
  /** The owner's Telegram username, without the @; null when not set. */
  owner_telegram: string | null;
  uploads: { image: UploadLimit; audio: UploadLimit; avatar: UploadLimit };
}

export interface Category {
  id: number;
  name: string;
  color: CategoryColor;
  idea_count: number;
  created_at: string;
}

export interface Tag {
  id: number;
  name: string;
  idea_count: number;
  created_at: string;
}

export interface Attachment {
  id: number;
  idea: number;
  kind: AttachmentKind;
  file_url: string;
  thumbnail_url: string | null;
  original_name: string;
  content_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  duration_seconds: number | null;
  created_at: string;
}

/** A Tiptap document. Only the shape the editor round-trips is described. */
export interface TiptapNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: TiptapNode[];
  marks?: { type: string; attrs?: Record<string, unknown> }[];
  text?: string;
}

export interface TiptapDocument extends TiptapNode {
  type: "doc";
  content?: TiptapNode[];
}

interface IdeaBase {
  id: number;
  title: string;
  plain_text: string;
  category: number | null;
  tags: string[];
  status: IdeaStatus;
  priority: IdeaPriority;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

/** A row in a listing: no document, just whether an attachment exists. */
export interface IdeaSummary extends IdeaBase {
  has_attachments: boolean;
}

export interface Idea extends IdeaBase {
  content: TiptapDocument;
  attachments: Attachment[];
}

/** An idea in the trash, with when it was put there. */
export interface TrashedIdea extends IdeaSummary {
  deleted_at: string;
}

export interface Reminder {
  id: number;
  idea: number;
  idea_title: string;
  idea_category_name: string | null;
  idea_category_color: string | null;
  idea_status: IdeaStatus;
  recurrence: RecurrenceKind;
  hour: number;
  minute: number;
  weekdays: number[];
  day_of_month: number | null;
  /** Jalali, as `[year, month, day]`. */
  exact_date: [number, number, number] | null;
  is_active: boolean;
  next_run_at: string | null;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface AppNotification {
  id: number;
  kind: NotificationKind;
  text: string;
  idea: number | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface TelegramLink {
  is_linked: boolean;
  linked_at: string | null;
  link: string | null;
  expires_at: string | null;
}
