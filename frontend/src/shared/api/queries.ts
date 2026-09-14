/**
 * Every server interaction the app performs.
 *
 * Query keys are built by `keys` so an invalidation cannot miss a cache entry
 * through a typo, and each mutation invalidates exactly what its write can
 * have changed.
 */

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";
import type {
  AppNotification,
  Attachment,
  Category,
  CurrentUser,
  Idea,
  IdeaSummary,
  Reminder,
  Tag,
  TelegramLink,
  TiptapDocument,
} from "@/types/domain";
import type { Paginated } from "@/types/api";

export const keys = {
  me: ["me"] as const,
  ideas: (params?: Record<string, unknown>) => ["ideas", params ?? {}] as const,
  idea: (id: number) => ["idea", id] as const,
  categories: ["categories"] as const,
  tags: ["tags"] as const,
  reminders: (params?: Record<string, unknown>) => ["reminders", params ?? {}] as const,
  notifications: (params?: Record<string, unknown>) => ["notifications", params ?? {}] as const,
  unreadCount: ["notifications", "unread-count"] as const,
  telegram: ["telegram-link"] as const,
};

/** Drops empty values so they never reach the API as blank query parameters. */
function clean(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null && value !== "",
    ),
  );
}

// --------------------------------------------------------------------------
// Session
// --------------------------------------------------------------------------

export function useCurrentUser(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => (await apiClient.get<CurrentUser>("/auth/me/")).data,
    retry: false,
    staleTime: 5 * 60_000,
    ...options,
  });
}

export function useLogin() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async (credentials: { username: string; password: string }) => {
      // The CSRF cookie has to exist before the first unsafe request.
      await apiClient.get("/auth/csrf/");
      return (await apiClient.post<CurrentUser>("/auth/login/", credentials)).data;
    },
    onSuccess: (user) => {
      client.setQueryData(keys.me, user);
    },
  });
}

export function useLogout() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await apiClient.post("/auth/logout/");
    },
    onSuccess: () => {
      client.clear();
    },
  });
}

export function useUpdateProfile() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async (patch: Partial<Pick<CurrentUser, "stale_after_days">>) =>
      (await apiClient.patch<CurrentUser>("/auth/me/", patch)).data,
    onSuccess: (user) => {
      client.setQueryData(keys.me, user);
      void client.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

// --------------------------------------------------------------------------
// Ideas
// --------------------------------------------------------------------------

export interface IdeaListParams {
  search?: string;
  status?: string;
  priority?: string;
  category?: number | null;
  tag?: string;
  sort?: string;
  archived?: boolean;
  stale?: boolean;
  page?: number;
  page_size?: number;
}

export function useIdeas(params: IdeaListParams = {}) {
  const query = clean({ ...params, archived: params.archived ? "true" : undefined });

  return useQuery({
    queryKey: keys.ideas(query),
    queryFn: async () =>
      (await apiClient.get<Paginated<IdeaSummary>>("/ideas/", { params: query })).data,
    // Moving between pages or filters keeps the current rows on screen until
    // the next set arrives, instead of flashing the loading state.
    placeholderData: keepPreviousData,
  });
}

export function useIdea(id: number | null) {
  return useQuery({
    queryKey: keys.idea(id ?? 0),
    queryFn: async () => (await apiClient.get<Idea>(`/ideas/${id}/`)).data,
    enabled: id !== null,
  });
}

export interface IdeaWrite {
  title?: string;
  content?: TiptapDocument;
  category?: number | null;
  tags?: string[];
  status?: string;
  priority?: string;
}

function invalidateIdeaLists(client: ReturnType<typeof useQueryClient>) {
  void client.invalidateQueries({ queryKey: ["ideas"] });
  void client.invalidateQueries({ queryKey: ["reminders"] });
}

export function useCreateIdea() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async (body: IdeaWrite) => (await apiClient.post<Idea>("/ideas/", body)).data,
    onSuccess: (idea) => {
      client.setQueryData(keys.idea(idea.id), idea);
      invalidateIdeaLists(client);
      void client.invalidateQueries({ queryKey: keys.tags });
      void client.invalidateQueries({ queryKey: keys.categories });
    },
  });
}

export function useUpdateIdea() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, ...body }: IdeaWrite & { id: number }) =>
      (await apiClient.patch<Idea>(`/ideas/${id}/`, body)).data,
    onSuccess: (idea) => {
      client.setQueryData(keys.idea(idea.id), idea);
      invalidateIdeaLists(client);
      void client.invalidateQueries({ queryKey: keys.tags });
      void client.invalidateQueries({ queryKey: keys.categories });
    },
  });
}

export function useDeleteIdea() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/ideas/${id}/`);
    },
    onSuccess: () => {
      invalidateIdeaLists(client);
      void client.invalidateQueries({ queryKey: keys.categories });
    },
  });
}

export function useArchiveIdea() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, restore }: { id: number; restore?: boolean }) =>
      (await apiClient.post<Idea>(`/ideas/${id}/${restore ? "restore" : "archive"}/`)).data,
    onSuccess: (idea) => {
      client.setQueryData(keys.idea(idea.id), idea);
      invalidateIdeaLists(client);
    },
  });
}

// --------------------------------------------------------------------------
// Categories and tags
// --------------------------------------------------------------------------

export function useCategories() {
  return useQuery({
    queryKey: keys.categories,
    queryFn: async () =>
      (await apiClient.get<Paginated<Category>>("/categories/", { params: { page_size: 100 } }))
        .data.results,
  });
}

export function useSaveCategory() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, ...body }: { id?: number; name: string; color: string }) =>
      id
        ? (await apiClient.patch<Category>(`/categories/${id}/`, body)).data
        : (await apiClient.post<Category>("/categories/", body)).data,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.categories });
      void client.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

export function useDeleteCategory() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/categories/${id}/`);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.categories });
      void client.invalidateQueries({ queryKey: ["ideas"] });
      void client.invalidateQueries({ queryKey: ["idea"] });
    },
  });
}

export function useTags() {
  return useQuery({
    queryKey: keys.tags,
    queryFn: async () =>
      (await apiClient.get<Paginated<Tag>>("/tags/", { params: { page_size: 100 } })).data.results,
  });
}

// --------------------------------------------------------------------------
// Attachments
// --------------------------------------------------------------------------

export function useUploadAttachment() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async ({ idea, kind, file }: { idea: number; kind: string; file: File }) => {
      const body = new FormData();
      body.append("idea", String(idea));
      body.append("kind", kind);
      body.append("file", file);

      return (
        await apiClient.post<Attachment>("/attachments/", body, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data;
    },
    onSuccess: (attachment) => {
      void client.invalidateQueries({ queryKey: keys.idea(attachment.idea) });
      void client.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

export function useDeleteAttachment() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async ({ id }: { id: number; idea: number }) => {
      await apiClient.delete(`/attachments/${id}/`);
    },
    onSuccess: (_data, variables) => {
      void client.invalidateQueries({ queryKey: keys.idea(variables.idea) });
      void client.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

// --------------------------------------------------------------------------
// Reminders
// --------------------------------------------------------------------------

export function useReminders(params: { window?: "today" | "week" } = {}) {
  const query = clean({ ...params, page_size: 100 });

  return useQuery({
    queryKey: keys.reminders(query),
    queryFn: async () =>
      (await apiClient.get<Paginated<Reminder>>("/reminders/", { params: query })).data.results,
  });
}

export interface ReminderWrite {
  idea: number;
  recurrence: string;
  hour: number;
  minute: number;
  weekdays?: number[];
  day_of_month?: number | null;
  exact_date?: [number, number, number] | null;
  is_active?: boolean;
}

export function useSaveReminder() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, ...body }: ReminderWrite & { id?: number }) =>
      id
        ? (await apiClient.put<Reminder>(`/reminders/${id}/`, body)).data
        : (await apiClient.post<Reminder>("/reminders/", body)).data,
    onSuccess: (reminder) => {
      void client.invalidateQueries({ queryKey: ["reminders"] });
      void client.invalidateQueries({ queryKey: keys.idea(reminder.idea) });
      void client.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

export function useDeleteReminder() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async ({ id }: { id: number; idea: number }) => {
      await apiClient.delete(`/reminders/${id}/`);
    },
    onSuccess: (_data, variables) => {
      void client.invalidateQueries({ queryKey: ["reminders"] });
      void client.invalidateQueries({ queryKey: keys.idea(variables.idea) });
      void client.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

// --------------------------------------------------------------------------
// Notifications
// --------------------------------------------------------------------------

export function useNotifications() {
  return useQuery({
    queryKey: keys.notifications(),
    queryFn: async () =>
      (
        await apiClient.get<Paginated<AppNotification>>("/notifications/", {
          params: { page_size: 50 },
        })
      ).data.results,
  });
}

export function useUnreadCount(options?: Partial<UseQueryOptions<{ count: number }>>) {
  return useQuery({
    queryKey: keys.unreadCount,
    queryFn: async () =>
      (await apiClient.get<{ count: number }>("/notifications/unread_count/")).data,
    ...options,
  });
}

export function useMarkNotificationRead() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.post(`/notifications/${id}/read/`);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await apiClient.post("/notifications/read_all/");
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

// --------------------------------------------------------------------------
// Telegram
// --------------------------------------------------------------------------

export function useTelegramLink() {
  return useQuery({
    queryKey: keys.telegram,
    queryFn: async () => (await apiClient.get<TelegramLink>("/telegram/link/")).data,
  });
}

export function useCreateTelegramLink() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async () => (await apiClient.post<TelegramLink>("/telegram/link/")).data,
    onSuccess: (link) => {
      client.setQueryData(keys.telegram, link);
    },
  });
}

export function useDisconnectTelegram() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await apiClient.delete("/telegram/link/");
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.telegram });
      void client.invalidateQueries({ queryKey: keys.me });
    },
  });
}
