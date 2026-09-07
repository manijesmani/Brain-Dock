from django.contrib import admin
from django.urls import include, path

# MEDIA_URL is deliberately not routed, in development either. Attachments are
# private and reachable only through the views in apps.ideas.attachment_views,
# which check ownership first. Serving MEDIA_ROOT here would make development
# behave differently from production on exactly the point that matters, so a
# leak would never show up locally.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/auth/", include("apps.users.urls")),
    path("api/", include("apps.ideas.urls")),
    path("api/", include("apps.reminders.urls")),
    path("api/", include("apps.notifications.urls")),
]
