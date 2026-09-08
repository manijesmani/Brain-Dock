import { createBrowserRouter } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { LoginPage } from "@/features/auth/LoginPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { BrowsePage } from "@/features/ideas/BrowsePage";
import { NotePage } from "@/features/ideas/NotePage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { AppLayout } from "@/features/shell/AppLayout";

export const router = createBrowserRouter([
  { path: ROUTES.login, element: <LoginPage /> },
  {
    // Every screen but login lives inside the shell, which also guards the
    // session: no user means a redirect to the login page.
    element: <AppLayout />,
    children: [
      { path: ROUTES.dashboard, element: <DashboardPage /> },
      { path: ROUTES.ideas, element: <BrowsePage /> },
      { path: ROUTES.archive, element: <BrowsePage archived /> },
      { path: ROUTES.note, element: <NotePage /> },
      { path: ROUTES.notifications, element: <NotificationsPage /> },
      { path: ROUTES.settings, element: <SettingsPage /> },
    ],
  },
]);
