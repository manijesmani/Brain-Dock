from rest_framework.routers import DefaultRouter

from apps.reminders.views import ReminderViewSet

app_name = "reminders"

router = DefaultRouter()
router.register("reminders", ReminderViewSet, basename="reminder")

urlpatterns = router.urls
