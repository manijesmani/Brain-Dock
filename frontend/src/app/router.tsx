import { createBrowserRouter } from "react-router-dom";

import { PlaceholderPage } from "@/app/PlaceholderPage";
import { ROUTES } from "@/app/routes";
import { HealthCheckPage } from "@/features/dashboard/HealthCheckPage";

export const router = createBrowserRouter([
  // Phase 0 acceptance screen; phase 5 swaps in the real dashboard.
  { path: ROUTES.dashboard, element: <HealthCheckPage /> },
  { path: ROUTES.ideas, element: <PlaceholderPage title="همهٔ ایده‌ها" /> },
  { path: ROUTES.note, element: <PlaceholderPage title="صفحهٔ یادداشت" /> },
  { path: ROUTES.archive, element: <PlaceholderPage title="آرشیو" /> },
  { path: ROUTES.notifications, element: <PlaceholderPage title="اعلان‌ها" /> },
  { path: ROUTES.settings, element: <PlaceholderPage title="تنظیمات" /> },
  { path: ROUTES.login, element: <PlaceholderPage title="ورود" /> },
  { path: "*", element: <PlaceholderPage title="صفحه پیدا نشد" /> },
]);
