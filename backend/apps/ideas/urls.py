from rest_framework.routers import DefaultRouter

from apps.ideas.views import CategoryViewSet, IdeaViewSet, TagViewSet

app_name = "ideas"

router = DefaultRouter()
router.register("ideas", IdeaViewSet, basename="idea")
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")

urlpatterns = router.urls
