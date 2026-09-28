from rest_framework.routers import DefaultRouter

from apps.users.panel_views import UserPanelViewSet

app_name = "panel"

router = DefaultRouter()
router.register("users", UserPanelViewSet, basename="user")

urlpatterns = router.urls
