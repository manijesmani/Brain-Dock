import { createBrowserRouter, Navigate } from "react-router-dom";

import { OLD_LOGIN, ROUTES } from "@/app/routes";
import { LoginPage } from "@/features/auth/LoginPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { BrowsePage } from "@/features/ideas/BrowsePage";
import { NotePage } from "@/features/ideas/NotePage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { AppLayout } from "@/features/shell/AppLayout";
import { TrashPage } from "@/features/trash/TrashPage";

export const router = createBrowserRouter([
  // Keyed, so moving between the two starts each with empty fields.
  { path: ROUTES.login, element: <LoginPage key="login" /> },
  { path: ROUTES.signup, element: <LoginPage key="signup" signup /> },
  { path: OLD_LOGIN, element: <Navigate to={ROUTES.login} replace /> },
  {
    // Every other screen lives inside the shell, which also sees to the
    // session: without one, a guest session starts, or the login page opens
    // for someone who has signed in on this browser before.
    element: <AppLayout />,
    children: [
      { path: ROUTES.dashboard, element: <DashboardPage /> },
      { path: ROUTES.ideas, element: <BrowsePage /> },
      { path: ROUTES.archive, element: <BrowsePage archived /> },
      { path: ROUTES.trash, element: <TrashPage /> },
      { path: ROUTES.note, element: <NotePage /> },
      { path: ROUTES.notifications, element: <NotificationsPage /> },
      { path: ROUTES.settings, element: <SettingsPage /> },
    ],
  },
]);
